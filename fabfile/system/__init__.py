from fabric.api import env, task, settings, put, hide, run as frun, sudo as fsudo
from fabric.contrib.files import exists
from .. import util
import re
import os


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

            # create the user in their own primary group, and add them to both
            # sudo and staff
            result = sudo(
                "useradd -U -G sudo,staff -m -d /home/%s -s /bin/bash %s" % (u, u))

            # user either was created, or already exists
            if result.return_code in [0, 9]:

                # If the local directory contains a keys subdirectory, and the keys dir
                # contains a public key with the same name as this user, automatically deploy
                # the key into the remote user's authorized_keys list.
                #
                # WAT: We should probably allow for key generation here
                # WAT WAT: We should make SSH access disabled by default, and
                # configurable.
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

    sudo(
        'echo "LANG=\"{0}\"\nLC_ALL=\"{0}\"" > /etc/default/locale'.format(locale))


@task
def ensure_running(service=None):
    """
    Ensure all services listed in settings.ENSURE_RUNNING are running
    """

    if not service:
        svcs = env.ensure_running
    else:
        svcs = [service]

    for svc in svcs:
        util.print_command("Starting %s" % svc)
        fsudo("/etc/init.d/{0} start".format(svc), pty=False)


@task
def bootstrap():
    """
    Meta-task that bootstraps the base system; must be run as root

    Since this task creates the staff users the first time out, and is responsible for
    configuring the sudoers config, it must be run as root, since without privileged accounts
    and sudo access you won't have the ability to create privileged accounts or configure sudo
    access.
    """

    # bootstrap executes various tasks that must be done as root (ie, install
    # sudo)
    if env.user != "root":
        raise Exception("You must set SSH_USER=root to run bootstrap().")

    set_timezone()
    set_locale()

    sudo("apt-get update -y -q")
    sudo("apt-get dist-upgrade -y -q")

    install_dependencies()
    firewall()
    util.upload_all_templates()
    create_staff()
    ensure_running()


@task
def install_dependencies():
    """
    Install or update system dependencies listed in APT_REQUIREMENTS_PATH
    """

    # resolve any lingering conflicts of config files from aborted runs
    sudo("dpkg --configure -a --force-confdef --force-confold")

    # step through each file listed in the APT_REQUIREMENTS_PATH, and append every
    # package name found therein to a list of packages we will hand to apt()
    # to install.
    reqs = ''
    for p in env.apt_requirements_path:
        fn = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), p))
        print "Installing dependencies from %s" % fn
        with open(fn, 'r') as f:
            for pkg in f.read().split('\n'):
                reqs = "%s %s" % (reqs, pkg.strip())
    return apt(reqs)


@task
def run(command, show=True):
    """
    Runs a shell comand on the remote server
    """
    if show:
        util.print_command(command)
        with hide("running"):
            return frun(command)
    with hide("running", "output"):
        return frun(command)


@task
def sudo(command, show=True):
    """
    Runs a command as sudo, unless the current user is root, in which case just run it
    """
    if show:
        util.print_command(command)
        with hide("running"):
            if env.user == "root":
                return frun(command)
            else:
                return fsudo(command)
    else:
        with hide("running", "output"):
            if env.user == "root":
                return frun(command)
            else:
                return fsudo(command)


@task
def apt(packages):
    """
    Installs one or more system packages via apt.
    """
    return sudo("apt-get install -y -q " + packages)


@task
def unban_ips(ips=None):

    if not ips:
        ips = env.all_admin_ips
    ips = ips.replace(',', ' ')

    for ip in ips.split():
        sudo("grep -v %s /var/log/fail2ban.log > /tmp/fail2ban.tmp" % ip)
        sudo("cp /tmp/fail2ban.tmp /var/log/fail2ban.log")
        with settings(warn_only=True):
            sudo("iptables -D fail2ban-ssh -s %s -j DROP" % ip, show=False)


@task
def firewall(firewall=None):
    """
    Configure a default firewall allowing inbound SSH from admin IPs. We use ufw mostly
    because its syntax is more readable than raw iptables, which is a good thing in scripts.
    """

    # What set of rules should we apply? by default, use the FIREWWALL
    # variable from settings.
    if not firewall:
        firewall = env.firewall

    # WAT you could flush existing rules here, to completely wipe out any changes that have
    # been made. This is a Good Idea, and you should do it. Meaning me,
    # meaning I should do it.

    util.get_public_ip()

    for r in env.firewall:
        rule = re.sub(r"%(?!\(\w+\)s)", "%%", r)
        rule %= env
        sudo("ufw %s" % rule)

    # WAT we should probably only do this if rules have actually changed.
    sudo("echo 'y' | ufw enable")
    sudo("ufw reload")


# _run and _sudo are wrappers for other submodules to import. We do this to avoid
# the run and sudo tasks from this module showing up in the other namespaces, thus:
#
# from ..system import _run as run, _sudo as sudo
#
def _run(command, show=True):
    return run(command, show)


def _sudo(command, show=True):
    return sudo(command, show)
