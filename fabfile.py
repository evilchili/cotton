# fabfile.py
#   -- fabric deployment tasks
#
import sys
import re
import os
from functools import wraps
from fabric.api import env, sudo as _sudo, run as _run, hide, task, settings, put, cd
from fabric.contrib.files import exists, upload_template
from fabric.colors import green, blue, yellow, red
from contextmanagers import project  # , log_call, virtualenv
from subprocess import check_output, check_call
#from fabric.exceptions import NetworkError
#from tempfile import mkstemp


######################################################################
# UTILITY FUNCTIONS
######################################################################

def set_fabric_env(settings_module):
    """
    Configure fabric's shared environment with values loaded from the settings module.
    """

    conf = __import__(settings_module, globals(), locals(), [], 0)

    if '-u' not in sys.argv:
        env.user = conf.SSH_USER

    for k in [k for k in conf.__dict__.keys() if k.upper() == k]:
        v = getattr(env, k.lower(), None)
        if not v:
            setattr(env, k.lower(), getattr(conf, k, None))

    # Some sugar to disambiguate references to 'user' in the templates
    env.fabric_user = env.user


def add_line_if_missing(target, text):

    tempfile = "/tmp/hosts%s" % os.getpid()
    grep_cmd = 'grep -v "%s" "%s" > %s' % (text, target, tempfile)
    echo_cmd = 'echo "%s" >> "%s"' % (text, tempfile)
    mv_cmd = 'mv %s "%s"' % (tempfile, target)
    sudo("%s && %s && %s" % (grep_cmd, echo_cmd, mv_cmd))


def print_command(command):
    print
    print blue("$ ", bold=True) + yellow(command, bold=True) + red(" ->", bold=True)
    print


def printc(text, color=blue):
    """
    Print colorized ouptut
    """
    print(color(text))


def print_header(func):
    """
    Function decorator that displays the function name as a header in the output.
    """
    @wraps(func)
    def logged(*args, **kawrgs):
        header = "-" * len(func.__name__)
        print(green("\n".join([header, func.__name__, header]), bold=True))
        return func(*args, **kawrgs)
    return logged


def get_templates():
    """
    Returns each of the templates with env vars injected.
    """
    injected = {}
    for t in env.templates:
        name = t['name']
        injected[name] = dict([(k, v % env) for k, v in t.items()])
    return injected


def upload_template_and_reload(name):
    """
    Uploads a template only if it has changed, and if so, reload a
    related service.
    """
    template = get_templates()[name]
    local_path = template["local_path"]
    if not os.path.exists(local_path):
        project_root = os.path.dirname(os.path.abspath(__file__))
        local_path = os.path.join(project_root, local_path)
    remote_path = template["remote_path"]
    reload_command = template.get("reload_command")
    owner = template.get("owner")
    mode = template.get("mode")
    remote_data = ""
    if exists(remote_path):
        with hide("stdout"):
            remote_data = sudo("cat %s" % remote_path, show=False)
    with open(local_path, "r") as f:
        local_data = f.read()
        # Escape all non-string-formatting-placeholder occurrences of '%':
        local_data = re.sub(r"%(?!\(\w+\)s)", "%%", local_data)
        local_data %= env
    clean = lambda s: s.replace("\n", "").replace("\r", "").strip()
    if clean(remote_data) == clean(local_data):
        return
    upload_template(local_path, remote_path, env,
                    use_sudo=not env.user == "root", backup=False)
    if owner:
        sudo("chown %s %s" % (owner, remote_path))
    if mode:
        sudo("chmod %s %s" % (mode, remote_path))
    if reload_command:
        sudo(reload_command)


def get_iface_for_subnet(subnet):
    """
    Return the NIC on which the specified subnet is configured.
    """
    subnet = subnet.replace('.', '\\.')
    cmd = "/sbin/ifconfig | grep -B1 'inet addr:%s' | cut -d' ' -f1" % subnet
    return sudo(cmd, show=True)


def get_ipv4(iface):
    """
    Return the IPv4 address assigned to the specified NIC.
    """
    cmd = "/sbin/ifconfig %s | grep 'inet addr:' | cut -d: -f 2 |cut -d' ' -f1" % iface
    return sudo(cmd, show=True)


def define_local_git_ssh():
    """
    Configure git to execute ssh with the corrrect identity file.
    """
    if not env.key_filename:
        return

    sh = './fabric_ssh.sh'

    # skip host IP checking, but only in staging.
    ssh_opts = ""
    if env.environment == 'staging':
        ssh_opts = '-oCheckHostIP=no'

    with open(sh, 'w') as f:
        f.write('#!/bin/sh\n')
        f.write('ssh -i %s %s $*' % (env.key_filename, ssh_opts))
    os.chmod(sh, 0755)
    os.environ.setdefault('GIT_SSH', sh)


def get_git_remotes():
    """
    Return a dict of remotes in the current (local) git repo.
    """
    remotes = {}
    for line in check_output(["git", "remote", "-v"]).split("\n"):
        # Sample output:
        #    foo.org     fabric@foo.org:/websites/foo/project.git (push)
        if line:
            (name, url, op) = line.split()
            if op == "(push)":
                remotes[name] = url
    return remotes


def create_project_user():
    with settings(warn_only=True):
        sudo("groupadd -f %s" % env.project_group)
        result = sudo(
            "useradd -g {1} -m -d /home/{0} -s /bin/bash {0}".format(
                env.project_user,
                env.project_group
            )
        )
    if result.return_code not in [0, 9]:
        print result
        raise SystemExit()


######################################################################
# HELPER TASKS
######################################################################
@task
def run(command, show=True):
    """
    Runs a shell comand on the remote server.
    """
    if show:
        printc(command)
        with hide("running"):
            return _run(command)
    with hide("running", "output"):
        return _run(command)


@task
def sudo(command, show=True):
    """
    Runs a command as sudo, unless the current user is root, in which case just run it.
    """
    if show:
        printc(command)
        with hide("running"):
            if env.user == "root":
                return _run(command)
            else:
                return _sudo(command)
    else:
        with hide("running", "output"):
            if env.user == "root":
                return _run(command)
            else:
                return _sudo(command)


@task
def install_dependencies():
    """
    Checks for changes in the system dependencies file across an update,
    and gets new requirements if changes have occurred.
    """

    # resolve any lingering conflicts of config files from aborted runs
    sudo("dpkg --configure -a --force-confdef --force-confold")

    for p in env.apt_requirements_path:
        fn = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), p))
        reqs = ''
        with open(fn, 'r') as f:
            for pkg in f.read().split('\n'):
                reqs = "%s %s" % (reqs, pkg.strip())
    return apt(reqs)


@task
def remove_virtualenv():
    """
    Blow away the current project
    """
    if exists(env.virtualenv_path):
        sudo("rm -rf %s" % env.virtualenv_path)


@task
def remove_templates():
    """
    Remove any files we have deployed from templates
    """
    for template in get_templates().values():
        remote_path = template["remote_path"]
        if exists(remote_path):
            sudo("rm %s" % remote_path)


@task
def git_push(rev=None):
    """
    Push the local git repo to the remote hosts
    """

    if rev is None:
        rev = env.git_branch

    # ensure the project path exists and is a git repo with a first commit.
    if not exists(env.project_root):
        sudo("mkdir -p %s" % env.project_root)
        sudo("chmod 2775 %s" % env.project_root)
        sudo("chown -R %s:%s %s" % (env.project_user, env.project_group, env.project_root))
        with cd(env.project_root):
            run("git init")

    remotes = get_git_remotes()

    define_local_git_ssh()

    # set up the remote host as a git remote in our local configuration
    h = env.host_string
    if h not in remotes:
        print_command("git remote add %s %s@%s:%s" % (h, env.user, h, env.project_root))
        check_call(["git", "remote", "add", h, "%s@%s:%s" % (env.user, h, env.project_root)])
        remotes = get_git_remotes()

    pushed = False
    if rev == env.git_branch:
        # determine if the remote branch exists
        with cd(env.project_root):
            ret = run("git branch")
            if rev not in ret:
                print_command("git push %s %s" % (h, rev))
                check_call(["git", "push", h, rev])
                pushed = True

    if not pushed:
        # the first push must create the master branch, so we must only specify the rev,
        # not the source ref. Because git reasons.
        print_command("git push %s HEAD:%s" % (h, rev))
        check_call(["git", "push", h, "HEAD:%s" % rev])

    # pushing into a branch on a remote that already exists will cause madness;
    # we must ensure the working tree is in sync with the newly-pushed ref.
    with cd(env.project_root):
        run("git checkout %s" % rev)
        run("git reset --hard")
        run("git submodule init")
        run("git submodule update")


@task
def create_virtualenv():
    """
    (re)create a virtualenv for a python project deployment.
    """

    # Create virtualenv
    sudo("mkdir -p %s" % env.virtualenv_home)
    sudo("chown %s:%s %s" % (env.project_user, env.project_group, env.virtualenv_home))
    with cd(env.virtualenv_home):
        if exists(env.project_name):
            if not env.no_prompts:
                prompt = raw_input("\nVirtualenv exists: %s\nWould you like "
                                   "to replace it? (yes/no) " % env.project_name)
                if prompt.lower() != "yes":
                    print "\nAborting!"
                    return False
            remove_virtualenv()
            remove_templates()
        run("virtualenv %s" % env.project_name)

        # create the target directory for this project on the remote server
        root = os.path.dirname(os.path.abspath(__file__))
        if env.use_git:
            run("git config --global user.email '%s'" % env.project_user)
            run("git config --global user.name  '%s'" % env.project_user)
            run("git config --global receive.denyCurrentBranch ignore")
            git_push()
        else:
            root = os.path.dirname(os.path.abspath(__file__))
            sudo("mkdir -p %s" % env.project_root)
            for target in env.upload_targets:
                put("%s/%s" %
                    (root, target), env.project_root, use_sudo=True, mirror_local_mode=True)


@task
def update_python_requirements():

    # Set up project by installing required python modules
    with project(env):
        for p in getattr(env, 'pip_requirements_path', []):

            # skip any requirements file that doesn't exist on the remote host. This lets us
            # ignore cotton's default requirements, if they're listed in the env.
            fn = env.project_root + '/' + p
            if exists(fn):
                pip("-r %s" % fn)


@task
def apt(packages):
    """
    Installs one or more system packages via apt.
    """
    return sudo("apt-get install -y -q " + packages)


@task
def pip(packages):
    """
    Installs one or more Python packages within the virtual environment.
    """
    return sudo("pip install %s" % packages)


@task
def firewall():
    """
    Configure a default firewall allowing inbound SSH from admin IPs. We use ufw mostly
    because its syntax is more readable than raw iptables, which is a good thing in scripts.
    """

    # WAT deny all outgoing should be the default, with the cumbersome rulesets this implies.
    sudo("ufw default deny incoming")
    sudo("ufw default allow outgoing")

    public_ip = get_ipv4("eth0")

    for i in env.admin_ips:
        sudo("ufw allow proto tcp from %s to %s port 22" % (i, public_ip))

    sudo("ufw disable")
    sudo("ufw enable")


@task
def create_staff():
    """
    Create any missing staff accounts.
    """

    for u in env.staff_users:
        with settings(warn_only=True):
            result = sudo("useradd -U -G sudo,staff -m -d /home/%s -s /bin/bash %s" % (u, u))

            # user either was created, or already exists
            if result.return_code in [0, 9]:
                run("mkdir -p /home/%s/.ssh" % u)
                key = "keys/%s.pub" % u
                if (os.path.exists(key)):
                    put(key, "/home/%s/.ssh/authorized_keys" % u)
                run("chmod 600 /home/%s/.ssh/authorized_keys" % u)
                run("chown -R %s:%s /home/%s/.ssh" % (u, u, u))
                run("chmod 700 /home/%s/.ssh" % u)
            else:
                print result
                raise SystemExit()


@task
def install():
    """
    Create the python virtualenv and deployment target directories if necessary
    """

    create_project_user()
    if not exists(env.virtualenv_home) or not exists(env.project_root):
        create_virtualenv()
        update_python_requirements()
        return True
    return False


@task
def bootstrap():
    """
    Meta-task that bootstraps the base system + firewall of all servers.
    """

    # bootstrap executes various tasks that must be done as root (ie, install sudo)
    if env.user != "root":
        raise Exception("You must set SSH_USER=root to run bootstrap().")

    install_dependencies()
    firewall()
    upload_template_and_reload('sudoers')
    create_staff()


if __name__ == '__main__':
    if sys.argv[0].split(os.sep)[-1] != 'fab':
        raise Exception("Please run 'fab' to execute fabric tasks.")

    # import settings from the local directory
    set_fabric_env('settings')
