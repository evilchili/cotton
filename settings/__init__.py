# cotton/settings.py
import os

# The local path to cotton -- used for locating and loading submodules, templates, etc.
COTTON_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

# By default projects will be deployed in VIRTUALENV_HOME/PROJECT_NAME
VIRTUALENV_HOME = '/usr/local/deploy'

# You will want to specify these values in your application's cotton_settings file.
PROJECT_NAME = None
VIRTUALENV_PATH = None

# a restricted user as whom the application will execute; do not put them in the
# staff or sudo groups!
PROJECT_USER = None
PROJECT_GROUP = None

# SSH Configuration for fabric tasks. Note that you must explicitly override SSH_USER
# with 'root' when running the bootstrap fabric task. By default this user is given
# sudo privileges, but you can override that by removing them from STAFF_USERS; see
# below.
SSH_USER = 'deploy'
SSH_PASS = None
SSH_KEY_PATH = '~/.ssh/id_rsa'


# where to find the system and python requirements. The default values contain
# packages and modules common to most deployments; you can extend or override
# these lists in your application's cotton_settings.
#
# Note that the paths here are relative to your application root, so the defaults
# assume you are adding cotton as a submodule at build/cotton/.  If you place the
# submodule elsewhere in your code, you will need to override these values in your
# local cotton_settings.py (or merge the contents into your own requirements files).
PIP_REQUIREMENTS_PATH = ['requirements/pip.txt']
APT_REQUIREMENTS_PATH = ['requirements/apt.txt']

# Note: may be platform-dependant!
LOCALE = 'en_US.UTF-8'

# timezone defaults to UTC; override in your local configs.
TIMEZONE = 'UTC'

# IPs from which admin traffic should be permitted.
ADMIN_IPS = []

# the accounts that should be created in the staff group and granted sudo access.
# We default to a single 'deploy' user so other projects that are deploying via
# fabric to our host(s) do not need root access.
STAFF_USERS = [SSH_USER]

# install outbound smtp services via postfix, if true
SMTP_HOST = False

# if SMTP_RELAY is set, configure postfix to relay outbound SMTP through this host.
SMTP_RELAY = None

# Use git for shipping application code to the remote hosts
USE_GIT = True
GIT_BRANCH = 'master'


# Default firewall rules that will be applied by the firewall() task.
FIREWALL = [
    "default deny incoming",
    "default allow outgoing",
    "allow proto tcp from %(all_admin_ips)s to %(public_ip)s port 22",
]

TEMPLATES = [
    {
        "name": "sudoers",
        "local_path": COTTON_PATH + "/templates/sudoers",
        "remote_path": "/etc/sudoers",
    },
]

# list all services that should be running here; each member of the list should be the name
# of a sysvinit script that can respond to the start and status commands.
ENSURE_RUNNING = []

# import the default mysql settings, if any
exec("from mysql.settings import *" in locals()

# attempt to load environment-specific settings
e = os.environ.get('COTTON_TARGET', None)
if e:
    try:
        exec("from {0} import *".format(e)) in locals()
    except Exception as e:
        print "WARNING: Could not locate local settings for environment '%s'" % e
