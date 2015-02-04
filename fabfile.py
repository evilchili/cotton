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
#
# These are routines that are not invokable as tasks, but perform some
# repeatable function or other used by tasks.
#
######################################################################

def set_fabric_env(settings_module):
    """
    Configure fabric's shared environment with values loaded from the settings module.

    This should be invoked once at startup to bootstrap the shared env; refer to the
    __main__ section at the bottom of this file for an example.
    """

    # load the specified module
    conf = __import__(settings_module, globals(), locals(), [], 0)

    # if the -u flag was not specified when fabric was invoked, we will execute all tasks
    # as the SSH_USER from the settings module.  We have to check for this one manually,
    # since by default fabric will set env.user to the EUID user, if -u is not specified.
    if '-u' not in sys.argv:
        env.user = conf.SSH_USER

    # Step through all the variables in the settings module that are ALL_UPPERCASE, and
    # set corresponding all_lowercase attributes on the env object, but only if the attribute
    # doesn't already exist. Thus we honor any overrides specified in the fab command line.
    for k in [k for k in conf.__dict__.keys() if k.upper() == k]:
        v = getattr(env, k.lower(), None)
        if not v:
            setattr(env, k.lower(), getattr(conf, k, None))

    # Some sugar to disambiguate references to 'user' in the templates
    env.fabric_user = env.user


def add_line_if_missing(target, text):
    """
    Add the specified text to a target file, if it isn't there already.

    WAT: This is slightly dangerous, and not easily undoable, so we probably shouldn't allow it.
    If you need this ability, you probably want a declarative configuration management tool.
    """
    tempfile = "/tmp/temp_%s" % os.getpid()
    grep_cmd = 'grep -v "%s" "%s" > %s' % (text, target, tempfile)
    echo_cmd = 'echo "%s" >> "%s"' % (text, tempfile)
    mv_cmd = 'mv %s "%s"' % (tempfile, target)
    sudo("%s && %s && %s" % (grep_cmd, echo_cmd, mv_cmd))


def print_command(command):
    """
    Pretty-print commands on STDOUT.
    """
    print
    print blue("$ ", bold=True) + yellow(command, bold=True) + red(" ->", bold=True)
    print


def printc(text, color=blue):
    """
    Print colorized output. Mostly for debugging and legibility of output.
    """
    print(color(text))


def print_header(func):
    """
    Function decorator that displays the function name as a header in the output.

    Snagged this one from mezzanine's default fabfile. :D
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

    WAT: This is likely deprecated now that we correctly honor fab's command-line overrides,
    so we should consider this for removal.
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
    """
    (re)create the user and group under which the project should run

    The project user is limited -- it should not have sudo access, nor should
    it be a member of the staff group.
    """

    # warnings only, since we accept more than the 0 exit status.
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

    # We place the fabric ssh user in the project group, because the
    # fabric user needs to be able to modify files owned by the user.
    sudo("usermod -a -G {1} {0}".format(env.fabric_user, env.project_group))


def set_project_perms():
    """
    Ensure that the project entire virtualenv is owned by the project user,
    that all directories are 2775, and that all files are writable by the group.

    This allows the privileged fabric ssh user to modify these files during
    deployment, but keeps everything nicely isolated when accessed from inside
    the running application.
    """

    sudo("chown -R %s:%s %s" % (env.project_user, env.project_group, env.virtualenv_home))
    sudo("find %s -type d -exec chmod 2775 {} \\;" % env.virtualenv_home)
    sudo("find %s -type f -exec chmod g+rw {} \\;" % env.virtualenv_home)


######################################################################
# HELPER TASKS
#
# These are generic tasks that generally accept one-or-more arguments
# that may be useful to invoke directly, but which are often used in
# major managment tasks.
#
# The original versions of many of these functions were copied from
# mezzanine's default fabfile, though they have diverged over time.
#
######################################################################


@task
def run(command, show=True):
    """
    Runs a shell comand on the remote server
    """
    if show:
        print_command(command)
        with hide("running"):
            return _run(command)
    with hide("running", "output"):
        return _run(command)


@task
def sudo(command, show=True):
    """
    Runs a command as sudo, unless the current user is root, in which case just run it
    """
    if show:
        print_command(command)
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


######################################################################
# MANAGEMENT TASKS
#
# These tasks do the heavy lifting of enforcing specific management
# policies on the remote server. This includes things like global
# package management, firewall rules, kernel tuning parameters, and
# so on.
#
######################################################################

@task
def set_timezone(zone=None):
    """
    Set the system timezone
    """
    if zone is None:
        zone = env.timezone
    zi = "/usr/share/zoneinfo/%s" % zone
    if not exists(zi):
        raise Exception("Could not locate zone info for '%s'" % zone)
    sudo("echo '%s' > /etc/timezone" % zone)
    sudo("cp %s /etc/localtime" % zi)


@task
def set_locale(locale=None):
    """
    Set the system locale
    """
    if locale is None:
        locale = env.locale

    supported = '/usr/share/i18n/SUPPORTED'
    with settings(warn_only=True):
        ret = run("grep '%s' %s" % (locale, supported))
        if ret.return_code != 0:
            raise Exception("Unsupported locale; check %s" % supported)

    sudo("echo 'LANG=\"{0]\"\nLC_ALL=\"{0}\" > /etc/default/locale".format(locale))


@task
def git_push(rev=None):
    """
    Push the local git repo to the remote hosts
    """

    # push either the specified revision, or the default GIT_BRANCH as specified in settings.
    if rev is None:
        rev = env.git_branch

    # ensure the project path exists and is an initialiezd git repo.
    if not exists(env.project_root):
        raise Exception("The project root is missing! Do you need to run the install() task?")
    with cd(env.project_root):
        run("git init")
        set_project_perms()

    remotes = get_git_remotes()

    # deprecated; see function docstring
    # define_local_git_ssh()

    # Set up the remote host as a git remote in our local configuration
    #
    # WAT: By only executing this sequence if the host is not listed in the remotes,
    # deployments will break if we change either the user or project root. Needs fixin.
    h = env.host_string
    if h not in remotes:
        print_command("git remote add %s %s@%s:%s" % (h, env.user, h, env.project_root))
        check_call(["git", "remote", "add", h, "%s@%s:%s" % (env.user, h, env.project_root)])
        remotes = get_git_remotes()

    # A little git jazz-hands here, to manage the push by first checking to see if
    # the default branch exists in the remote repository.
    pushed = False
    if rev == env.git_branch:
        # determine if the remote branch exists
        with cd(env.project_root):
            ret = run("git branch")
            if rev not in ret:
                print_command("git push %s %s" % (h, rev))
                check_call(["git", "push", h, rev])
                pushed = True

    # The first push must create the master branch, so we must only specify the rev,
    # not the source ref. Because git reasons...
    if not pushed:
        print_command("git push %s HEAD:%s" % (h, rev))
        check_call(["git", "push", h, "HEAD:%s" % rev])

    # ...but pushing into a branch on a remote that already exists will cause madness;
    # we must ensure the working tree is in sync with the newly-pushed ref.
    with cd(env.project_root):
        run("git checkout %s" % rev)
        run("git reset --hard")  # weeeeee!
        run("git submodule init")
        run("git submodule update")

        # fix up the permissions immediately after completing the push, so we don't
        # try to interact with files we cannot read or modify.
        set_project_perms()


@task
def create_virtualenv():
    """
    (re)create a virtualenv for a python project deployment

    This function sets up the entire virtualenv, initializes the local git repo inside the project
    root, and pushes up the local branch.  If invoked when the local virtualenv already exists, it
    will prompt for confirmation before destorying its, unless NO_PROMPTS is True in your settings.
    """

    # Create virtualenv
    sudo("mkdir -p %s" % env.virtualenv_home)
    sudo("chown %s:staff %s" % (env.user, env.virtualenv_home))

    # this bit also evolved from the mezzanine original. Seriously, what a great project.
    with cd(env.virtualenv_home):

        # remove the existing virtual environment and project root, if any.
        if exists(env.project_name):
            if not env.no_prompts:
                prompt = raw_input("\nVirtualenv exists: %s\nWould you like "
                                   "to replace it? (yes/no) " % env.project_name)
                if prompt.lower() != "yes":
                    print "\nAborting!"
                    return False
            remove_virtualenv()
            remove_templates()

        # create the new virtualenv and project root
        sudo("virtualenv %s" % env.project_name)
        sudo("mkdir -p %s" % env.project_root)
        set_project_perms()

    with cd(env.project_root):

        # do the initial configuration of the git client, so that we can do our push unmolested.
        if env.use_git:
            sudo("su -l {0} -c \"git config --global user.email '{0}'\"".format(env.project_user))
            sudo("su -l {0} -c \"git config --global user.name  '{0}'\"".format(env.project_user))
            sudo("su -l {0} -c \"git config --global receive.denyCurrentBranch ignore\"".format(
                env.project_user
            ))
            git_push()
        else:

            # WAT not sure I ever want to re-implement flat-file support, tbqh.
            raise NotImplementedError("flat-file support not implemented at this time.")
            #root = os.path.dirname(os.path.abspath(__file__))
            #sudo("mkdir -p %s" % env.project_root)
            # for target in env.upload_targets:
            #    put("%s/%s" %
            #        (root, target), env.project_root, use_sudo=True, mirror_local_mode=True)


@task
def install_python_dependencies():
    """
    Install any missing or updated python modules listed in PIP_REQUIREMENTS_PATH
    """

    with project(env):
        for p in getattr(env, 'pip_requirements_path', []):

            # skip any requirements file that doesn't exist on the remote host. This lets us
            # ignore cotton's default requirements, if they're listed in the env.
            #
            # WAT Should we print a warning here? meh.
            fn = env.project_root + '/' + p
            if exists(fn):
                pip("-r %s" % fn)


@task
def install_dependencies():
    """
    Install or update system dependencies listed in APT_REQUIREMENTS_PATH
    """

    # resolve any lingering conflicts of config files from aborted runs
    sudo("dpkg --configure -a --force-confdef --force-confold")

    # step through each file listed in the APT_REQUIREMENTS_PATH, and append every
    # package name found therein to a list of packages we will hand to apt() to install.
    for p in env.apt_requirements_path:
        fn = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), p))
        reqs = ''
        with open(fn, 'r') as f:
            for pkg in f.read().split('\n'):
                reqs = "%s %s" % (reqs, pkg.strip())
    return apt(reqs)


@task
def firewall():
    """
    Configure a default firewall allowing inbound SSH from admin IPs. We use ufw mostly
    because its syntax is more readable than raw iptables, which is a good thing in scripts.
    """

    # WAT you could flush existing rules here, to completely wipe out any changes that have
    # been made. This is a Good Idea, and you should do it. Meaning me, meaning I should do it.

    # WAT deny all outgoing should be the default, with the cumbersome rulesets this implies.
    sudo("ufw default deny incoming")
    sudo("ufw default allow outgoing")

    # WAT bad assumption here; we should make this configurable by adding a MANAGED_IFACE to the
    # settings or something.
    public_ip = get_ipv4("eth0")

    # ensure SSH access is permitted from the ADMIN_IPS.
    for i in env.admin_ips:
        sudo("ufw allow proto tcp from %s to %s port 22" % (i, public_ip))

    # WAT we should probably only do this if rules have actually changed.
    sudo("ufw disable")
    sudo("ufw enable")


@task
def create_staff():
    """
    Create any missing staff accounts.

    Staff accounts, for our purposes, are privileged users that all get sudo access.
    So there shouldn't be many of them, and they shouldn't be permitted SSH access except
    via (at least) key exchange.
    """

    for u in env.staff_users:
        with settings(warn_only=True):

            # create the user in their own primary group, and add them to both sudo and staff
            result = sudo("useradd -U -G sudo,staff -m -d /home/%s -s /bin/bash %s" % (u, u))

            # user either was created, or already exists
            if result.return_code in [0, 9]:

                # If the local directory contains a keys subdirectory, and the keys dir
                # contains a public key with the same name as this user, automatically deploy
                # the key into the remote user's authorized_keys list.
                #
                # WAT: We should probably allow for key generation here
                # WAT WAT: We should make SSH access disabled by default, and configurable.
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
    Create the python virtualenv and deployment directories if necessary

    A generic installation task that should be run at least once when deploying a new project,
    since it covers a bunch of stuff that will be common to any python application deployment.
    """

    create_project_user()
    if not exists(env.virtualenv_home) or not exists(env.project_root):
        create_virtualenv()
        install_python_dependencies()
        return True
    return False


@task
def bootstrap():
    """
    Meta-task that bootstraps the base system; must be run as root

    Since this task creates the staff users the first time out, and is responsible for
    configuring the sudoers config, it must be run as root, since without privileged accounts
    and sudo access you won't have the ability to create privileged accounts or configure sudo
    access.
    """

    # bootstrap executes various tasks that must be done as root (ie, install sudo)
    if env.user != "root":
        raise Exception("You must set SSH_USER=root to run bootstrap().")

    set_timezone()
    set_locale()
    install_dependencies()
    firewall()
    upload_template_and_reload('sudoers')
    create_staff()


if __name__ == '__main__':

    # don't allow direct invocation of this script. use the force^Wfab, Luke!
    if sys.argv[0].split(os.sep)[-1] != 'fab':
        raise Exception("Please run 'fab' to execute fabric tasks.")

    # import settings from the local directory; this can be extended by setting the environment
    # variable COTTON_TARGET; refer to cotton/settings/__init__.py.
    set_fabric_env('settings')
