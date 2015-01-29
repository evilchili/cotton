# cotton/settings.py


# Fabric SSH Configuration. User must be root for the 'bootstrap' task; refer to fabfile.py
SSH_USER = 'root'
SSH_PASS = None
SSH_KEY_PATH = '~/.ssh/id_rsa'

# where to find the system and python requirements
PIP_REQUIREMENTS_PATH = 'requirements/pip.txt'
APT_REQUIREMENTS_PATH = 'requirements/apt.txt'

# IPs from which admin traffiic should be permitted.
ADMIN_IPS = []
