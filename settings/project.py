# By default projects will be deployed in VIRTUALENV_HOME/PROJECT_NAME
VIRTUALENV_HOME = '/usr/local/deploy'

# You will want to specify these values in your application's cotton_settings file.
PROJECT_NAME = None
VIRTUALENV_PATH = None

# a restricted user as whom the application will execute; do not put them in the
# staff or sudo groups!
PROJECT_USER = None
PROJECT_GROUP = None

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

# Use git for shipping application code to the remote hosts
USE_GIT = True
GIT_BRANCH = 'master'
