# cotton_settings.py
#   -- Tell cotton how to deploy your application
#
# Import the default settings directly into the current namespace, so that you can combine,
# extend, and override the defaults with settings unique to your application deployment.
from cotton.settings import *
import os

# Name your project here. Will be used as a directory name, so be sensible.
PROJECT_NAME = ''

# deploy the appplication to /usr/local/deploy/sprobot/, creating
# bin/, lib/, project/ and so on at that location.
VIRTUALENV_PATH = os.path.join(VIRTUALENV_HOME, PROJECT_NAME)

# Where the application code (ie, the contents of the current directory) will be deployed.
PROJECT_ROOT = os.path.join(VIRTUALENV_PATH, 'project')

# A list of target nodes which cotton should (optionally) bootstrap and deploy your app to
HOSTS = []

# A list of IPv4 addresses that should be granted administrative access. This includes
# permitting SSH access, and may be leveraged for additional purposes in your ap
ADMIN_IPS = []

# The system user and group that should execute your application. The user will be created
# by cotton automatically, if it doesn't already exist. Existing users should not have extra
# privileges, including sudo access.
PROJECT_USER = ''
PROJECT_GROUP = ''

# PIP_REQUIREMENTS_PATH is defined by cotton's default settings, and includes cotton's very small
# list of required python packages (ie, virtualenv). You can override this or extend it with the
# path to your own requirements.txt, relative to your application's root.
#
#PIP_REQUIREMENTS_PATH += ['build/requirements/pip.txt']

# If True, do not prompt for confirmation of dangerous actions. Required for unattended operation,
# but dangerous in mixed (ie, dev/testing) environments, so disabled by default.
#
# NO_PROMPTS = False

# The timezone the HOSTS should be in. Cotton defaults to UTC; you can override that here.
#TIMEZONE = "America/New_York"

# By default cotton assumes your application is in a git repository, and that git can be used
# to deploy the application source to the HOSTS.
#
#USE_GIT = True

# If you want your HOSTS to run an SMTP server for outbound mail, set SMTP_HOST=True. You can
# specify a relay host with SMTP_RELAY.
#SMTP_HOST = False
#SMTP_RELAY = None

# Cotton includes a minimal set of templates for configuration files that can be managed by cotton.
# You can extend the templates by adding template files, using standard python string.format()
# syntax, to your /build/templates folder, and define their use below.
#
# Here is an example for a hypothetical crontab used to execute scheduled tasks for your app:
#
# TEMPLATES += [
#   {
#        "name": "cron",
#        "local_path": "templates/crontab",
#        "remote_path": "/etc/cron.d/%(project_name)s",
#        "owner": "root",
#        "mode": "600",
#   }
# ]
#TEMPLATES += []
