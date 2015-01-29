# cotton/settings.py
import os


# Fabric SSH Configuration. User must be root for the 'bootstrap' task; refer to fabfile.py
SSH_USER = 'root'
SSH_PASS = None
SSH_KEY_PATH = '~/.ssh/id_rsa'

# where to find the system and python requirements
PIP_REQUIREMENTS_PATH = 'requirements/pip.txt'
APT_REQUIREMENTS_PATH = 'requirements/apt.txt'

# IPs from which admin traffiic should be permitted.
ADMIN_IPS = []

# the accounts that should be created in the staff group and granted sudo access.
# We default to a single 'deploy' user so other projects that are deploying via
# fabric to our host(s) do not need root access.
STAFF = ['deploy']


# attempt to load environment-specific settings
e = os.environ.get('COTTON_TARGET', None)
if e:
    try:
        exec("from {0} import *".format(e)) in locals()
    except Exception as e:
        print "WARNING: Could not locate local settings for environment '%s'" % e
else:
    print "WARNING: COTTON_TARGET not set; continuing with default settings."
