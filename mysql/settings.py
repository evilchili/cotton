import os

MYSQL_ROOT_PASS = None
MYSQL_PORT = 3306

# To enable replication, you will need to provide these settings on a per-host basis.
MYSQL_REPLICATION_USER = None
MYSQL_REPLICATION_PASS = None
MYSQL_MASTER_IP = None

# you will want to override these according to the number of masters in your set.
MYSQL_AUTOINCREMENT_OFFSET = 1
MYSQL_AUTOINCREMENT_INCREMENT = 1

MYSQL_MAX_ALLOWED_PACKET = '16M'
MYSQL_KEY_BUFFER = '16M'

MYSQL_FIREWALL = [
    'allow proto tcp from %(all_admin_ips)s to %s port %(mysql_port)s',
]

# you must specify this in your local cotton_settings, and it must be unique
# within a given multi-master set!
MYSQL_SERVER_ID = None

MYSQL_DATABASES = {}
# DATABASES = {
#    "default": {
#        "NAME": 'cotton',
#        "USER": 'cotton',
#        "PASSWORD": os.environ.get('MYSQL_DEFAULT_PASS', '')
#    },
#}


tpath = os.path.abspath(os.path.join(os.path.dirname(__file__), 'templates'))

MYSQL_TEMPLATES = [
    {
        "name": "mysql_etc_my_cnf",
        "local_path": tpath + '/my.cnf',
        "remote_path": "/etc/mysql/my.cnf",
        "reload_command": "/etc/init.d/mysql reload"
    },
    {
        "name": "mysql_root_my_cnf",
        "local_path": tpath + '/root_my.cnf',
        "remote_path": "/root/.my.cnf",
        "owner": 'root',
        "mode": '0600',
    },
]
