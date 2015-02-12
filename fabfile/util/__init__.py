import re
import os
from functools import wraps
from fabric.api import env, hide, sudo
from fabric.contrib.files import exists, upload_template
from fabric.colors import green, blue, yellow, red
import hashlib


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


def check_shasum(filename, sha):
    """
    Compare the SHA256 checksum of a the specified file against the provided string.
    """
    local_sha = hashlib.sha256(open(filename, 'rb').read()).hexdigest()
    if local_sha != sha:
        raise Exception
    return local_sha == sha


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


def get_templates(templates=None):
    """
    Returns each of the templates with env vars injected.
    """

    if not templates:
        templates = env.templates

    injected = {}
    for t in env.templates:
        name = t['name']
        injected[name] = dict([(k, v % env) for k, v in t.items()])
    return injected


def upload_template_and_reload(name, templates=None):
    """
    Uploads a template only if it has changed, and if so, reload a
    related service.
    """
    template = get_templates(templates)[name]
    local_path = os.path.abspath(template["local_path"])
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
            remote_data = sudo("cat %s" % remote_path)
    with open(local_path, "r") as f:
        local_data = f.read()
        # Escape all non-string-formatting-placeholder occurrences of '%':
        local_data = re.sub(r"%(?!\(\w+\)s)", "%%", local_data)
        local_data %= env
    clean = lambda s: s.replace("\n", "").replace("\r", "").strip()
    if clean(remote_data) == clean(local_data):
        return
    print "Uploading %s => %s" % (local_path, remote_path)
    upload_template(local_path, remote_path, env, use_sudo=not env.user == "root", backup=False)
    if owner:
        sudo("chown %s %s" % (owner, remote_path))
    if mode:
        sudo("chmod %s %s" % (mode, remote_path))
    if reload_command:
        sudo(reload_command)


def upload_all_templates(templates=None):
    """
    Upload all configured templates and reload the related services.
    """
    if not templates:
        templates = env.templates

    for template in templates:
        n = template['name']
        upload_template_and_reload(n)


def get_iface_for_subnet(subnet):
    """
    Return the NIC on which the specified subnet is configured.
    """
    subnet = subnet.replace('.', '\\.')
    cmd = "/sbin/ifconfig | grep -B1 'inet addr:%s' | cut -d' ' -f1" % subnet
    return sudo(cmd)


def get_ipv4(iface):
    """
    Return the IPv4 address assigned to the specified NIC.
    """
    cmd = "/sbin/ifconfig %s | grep 'inet addr:' | cut -d: -f 2 |cut -d' ' -f1" % iface
    return sudo(cmd)


def get_public_ip(iface='eth0'):
    """
    Return the IP of the primary public interface.
    """

    # WAT bad assumption here; we should make this configurable by adding a MANAGED_IFACE to the
    # settings or something.
    env.public_ip = get_ipv4(iface)
    return env.public_ip
