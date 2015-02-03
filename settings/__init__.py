# cotton/settings.py
import os

# The local path to cotton -- used for locating and loading submodules, templates, etc.
COTTON_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

# By default projects will be deployed in VIRTUALENV_HOME/PROJECT_NAME
VIRTUALENV_HOME = '/usr/local/deploy'

# You will want to specify these values in your application's cotton_settings file.
PROJECT_NAME = None
VIRTUALENV_PATH = None

# SSH Configuration for fabric tasks. Note that you must explicitly override SSH_USER
# with 'root' when running the bootstrap fabric task.
SSH_USER = 'deploy'
SSH_PASS = None
SSH_KEY_PATH = '~/.ssh/id_rsa'

# where to find the system and python requirements. The default values contain
# packages and modules common to most deployments; you can extend or override
# these lists in your application's cotton_settings.
PIP_REQUIREMENTS_PATH = ['requirements/pip.txt']
APT_REQUIREMENTS_PATH = ['requirements/apt.txt']

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

# attempt to load environment-specific settings
e = os.environ.get('COTTON_TARGET', None)
if e:
    try:
        exec("from {0} import *".format(e)) in locals()
    except Exception as e:
        print "WARNING: Could not locate local settings for environment '%s'" % e
