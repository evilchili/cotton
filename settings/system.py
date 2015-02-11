import os

# The local path to cotton -- used for locating and loading submodules, templates, etc.
COTTON_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

# Note: may be platform-dependant!
LOCALE = 'en_US.UTF-8'

# timezone defaults to UTC; override in your local configs.
TIMEZONE = 'UTC'

# IPs from which admin traffic should be permitted.
ADMIN_IPS = []

# SSH Configuration for fabric tasks. Note that you must explicitly override SSH_USER
# with 'root' when running the bootstrap fabric task. By default this user is given
# sudo privileges, but you can override that by removing them from STAFF_USERS; see
# below.
SSH_USER = 'deploy'
SSH_PASS = None
SSH_KEY_PATH = '~/.ssh/id_rsa'

# the accounts that should be created in the staff group and granted sudo access.
# We default to a single 'deploy' user so other projects that are deploying via
# fabric to our host(s) do not need root access.
STAFF_USERS = [SSH_USER]

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
ENSURE_RUNNING = ['fail2ban' 'ntpd']
