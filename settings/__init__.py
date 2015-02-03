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
PIP_REQUIREMENTS_PATH = ['build/cotton/requirements/pip.txt']
APT_REQUIREMENTS_PATH = ['build/cotton/requirements/apt.txt']

# Note: may be platform-dependant!
LOCALE = 'en.US_UTF-8'

# IPs from which admin traffic should be permitted.
ADMIN_IPS = []

# the accounts that should be created in the staff group and granted sudo access.
# We default to a single 'deploy' user so other projects that are deploying via
# fabric to our host(s) do not need root access.
STAFF_USERS = [SSH_USER]

# Use git for shipping application code to the remote hosts
USE_GIT = True
GIT_BRANCH = 'master'

TEMPLATES = [
    {
        "name": "sudoers",
        "local_path": "templates/sudoers",
        "remote_path": "/etc/sudoers",
    },
]


# attempt to load environment-specific settings
e = os.environ.get('COTTON_TARGET', None)
if e:
    try:
        exec("from {0} import *".format(e)) in locals()
    except Exception as e:
        print "WARNING: Could not locate local settings for environment '%s'" % e
