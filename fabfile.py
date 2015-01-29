# fabfile.py
#   -- fabric deployment tasks
#
import sys
import re
import os
from functools import wraps
from fabric.api import env, sudo as _sudo, run as _run, hide, task
from fabric.contrib.files import exists, upload_template
from fabric.colors import green, blue
#from fabric.exceptions import NetworkError
#from tempfile import mkstemp

if sys.argv[0].split(os.sep)[-1] != 'fab':
    raise Exception("Please run 'fab' to execute fabric tasks.")

# import settings from the local directory
conf = __import__("settings", globals(), locals(), [], 0)

# check for env.hosts before configuring it with the HOSTS variable from settings,
# so that the target host(s) can be overridden at the command-line.
if not env.hosts:
    env.hosts = conf.HOSTS

# configure the shared environment
env.user = conf.SSH_USER
env.pip_reqs_path = conf.PIP_REQUIREMENTS_PATH
env.apt_reqs_path = conf.APT_REQUIREMENTS_PATH
env.admin_ips = conf.ADMIN_IPS

# to disambiguate references to 'user' in the templates
env.fabric_user = env.user

######################################################################
# TEMPLATES
######################################################################
templates = [
    {
        "name": "sudoers",
        "local_path": "templates/sudoers",
        "remote_path": "/etc/sudoers",
    },
]


######################################################################
# UTILITY FUNCTIONS
######################################################################

def add_line_if_missing(target, text):

    tempfile = "/tmp/hosts%s" % os.getpid()
    grep_cmd = 'grep -v "%s" "%s" > %s' % (text, target, tempfile)
    echo_cmd = 'echo "%s" >> "%s"' % (text, tempfile)
    mv_cmd = 'mv %s "%s"' % (tempfile, target)
    sudo("%s && %s && %s" % (grep_cmd, echo_cmd, mv_cmd))


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
    for t in templates:
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
    apt_reqs_path = os.path.abspath(os.path.join(
        os.path.dirname(os.path.abspath(__file__)), env.apt_reqs_path
    ))
    reqs = ''
    with open(apt_reqs_path, 'r') as f:
        for pkg in f.read().split('\n'):
            reqs = "%s %s" % (reqs, pkg.strip())
    return apt(reqs)


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
    Configure a default firewall allowing inbound SSH from admin IPs.
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
def bootstrap():
    """
    Meta-task that bootstraps the base system + firewall of all servers.
    """

    # bootstrap executes various tasks that must be done as root (ie, install
    # sudo)
    if env.user != "root":
        raise Exception("You must set SSH_USER=root to run bootstrap().")

    install_dependencies()
    firewall()
    upload_template_and_reload('sudoers')
