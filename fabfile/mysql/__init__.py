from fabric.api import task, execute, cd, env, settings
from fabric.contrib.files import exists
from .. import util, system
import re

__all__ = [
    'find_missing_pks', 'configure_replication', 'start_replication', 'install', 'run',
    'create_user', 'create', 'drop', 'dump', 'restore', 'master_status'
]


@task
def find_missing_pks():
    """
    List all tables which contain no primary key.
    """

    # cf
    # http://scale-out-blog.blogspot.com/2012/04/if-you-must-deploy-multi-master.html
    sql = """
        SELECT t.table_schema, t.table_name FROM information_schema.tables t
        WHERE NOT EXISTS (
         SELECT * FROM information_schema.columns c
         WHERE t.table_schema = c.table_schema
         AND t.table_name = c.table_name
         AND c.column_key = 'PRI'
         AND c.extra = 'auto_increment'
        )"""
    print run(sql)


@task
def configure_replication():
    """
    Configure an existing mysql server instance for multi-master replication
    """

    # WAT Should we consider support standalone mysql deployments?
    if not env.mysql_replication_user and env.mysql_replication_pass:
        raise Exception(
            "You must define MYSQL_REPLICATION_USER and MYSQL_REPLICATION_PASS in our settings."
        )

    # WAT should probably also sanity-check MYSQL_AUTOINCREMENT_OFFSET
    i = env.mysql_autoincrement_increment
    if (not i) or i <= 1:
        raise Exception(
            "It is exceedingly unwise to set up multi-master replication with an "
            "MYSQL_AUTOINCREMENT_INCREMENT of %s, and I refuse to do it. Sorry." % i
        )

    create_user(env.mysql_replication_user, env.mysql_replication_pass)
    run(
        "GRANT REPLICATION SLAVE ON *.* TO '%s'@'%%' IDENTIFIED BY '%s';" % (
            env.mysql_replication_username,
            env.mysql_replication_password,
        )
    )
    run("FLUSH PRIVILEGES;")


@task
def start_replication(host=None):
    """
    Slave the host to its MySQL master and (re)start replication
    """

    if not host:
        host = env.mysql_master_ip

    # get the mysql master status on the master node
    res = execute(master_status, hosts=[host])
    if res[host]:
        run("STOP SLAVE;")
        run("""CHANGE MASTER TO MASTER_HOST='%s',
            MASTER_USER='%s', MASTER_PASSWORD='%s',
            MASTER_LOG_FILE='%s', MASTER_LOG_POS=%s;""" % (
            host,
            env.mysql_replication_username,
            env.mysql_replication_password,
            env.mysql_master_log,
            env.mysql_master_log_pos,
            ))
        run("START SLAVE;")
    else:
        raise Exception("Could not get master status on node %s!" % host)


@task
def run(sql, db=False, show=True):
    """
    Execute an SQL statement, optionally using the specified database.
    """
    if db:
        out = ('echo "%s" | sudo mysql %s' % (sql, db))
    else:
        out = ('echo "%s" | sudo mysql' % sql)
    if show:
        util.print_command(sql)
    return out


@task
def install(server_id=None):
    """
    Install the mysql server and client packages
    """

    # install mysql-server with the root password defined in settings.py
    cmd = "debconf-set-selections <<< 'mysql-server"
    system.sudo("%s mysql-server/root_password password %s'" %
                (cmd, env.mysql_root_pass), show=False)
    system.sudo("%s mysql-server/root_password_again password %s'" %
                (cmd, env.mysql_root_pass), show=False)
    system.apt("mysql-server mysql-client")

    # whether it was passed as a parameter or included in the settings,
    # we must have a server_id to continue. If the server is part of a
    # multi-mastesr set, the server_id must be guaranteed to be unique
    # within that set.
    #
    # NB: Since this task is atomic, we have no way of knowing whether
    # the current host is part of a multi-master set; uniqueness of the
    # server_id is a problem for the caller.
    if server_id:
        env.mysql_server_id = server_id
    if not env.mysql_server_id:
        raise Exception("You must specify a unique MYSQL_SERVER_ID.")

    # create both the /etc/my.cnf and /root/.my.cnf files
    util.upload_all_templates(env.mysql_templates)

    # configure replication, if necessary
    if env.mysql_replication_user and env.mysql_replication_pass:
        configure_replication()

    # some things timezone data to be present in the 'mysql' database (notably
    # django stuff).
    system.sudo("mysql_tzinfo_to_sql /usr/share/zoneinfo | mysql -u root mysql")

    # update the firewall on the server, if necessary
    system.firewall(env.mysql_firewall)


@task
def create_user(user, pwd, db=None):
    """
    (Re)create a mysql user
    """
    safe_pass = pwd.replace("'", "\'")
    with settings(warn_only=True):
        cmd = "CREATE USER '%s'@'%%' IDENTIFIED BY '%s';"
        util.print_command(cmd % (user, '*' * len(safe_pass)))
        run(cmd % (user, safe_pass))

        if db:
            run(
                "GRANT ALL PRIVILEGES ON %s.* TO '%s'@'%%' IDENTIFIED BY '%s';" %
                (db, user, safe_pass)
            )
            run("FLUSH PRIVILEGES;")


@task
def create():
    """
    Create database(s).
    """
    for (label, db) in env.mysql_databases.iteritems():

        with settings(warn_only=True):
            # WAT: the the default character encoding should probably honor
            # env.locale
            run("CREATE DATABASE %s CHARACTER SET utf8 COLLATE utf8_general_ci;" %
                db['NAME'])

        # create the database user and grant full privs on the database
        create_user(db['USER'], db['PASSWORD'], db=db['NAME'])


@task
def drop(name):
    """
    Drop a database.
    """
    with settings(warn_only=True):
        for (label, db) in env.mysql_databases.iteritems():
            if db['NAME'] == name:
                run("DROP USER '%s'@'%%'" % db['USER'])
                run("DROP DATABASE IF EXISTS %s;" % (db['NAME']))
                return True
    raise Exception(
        "Could not locate a database named '%s' in your settings; aborting." % name)


@task
def dump(filename='%(label)s.sql'):
    """
    Dump a database to a flatfile

    Note that this will silently overwrite any existing file matching the specifed filename.
    """

    filename = re.sub(r"%(?!\(\w+\)s)", "%%", filename)
    filename %= env

    with cd(env.project_root):
        for (label, db) in env.databases.iteritems():
            system.sudo("mysqldump --opt --lock-all-tables %s > %s" %
                        (db['NAME'], filename))


@task
def restore(name, filename, clear=False):
    """
    Import an sql dump file into the specified database.
    """

    with cd(env.project_root):
        if not exists(filename):
            raise Exception(
                "Dump file '%s' does not exist or could not be read." % filename)

        # WAT This is all kinds of dangerous, and should *at least* create copies of the tables
        # before dropping the database. It may be wiser to restore the dump to a new database,
        # configure it, rename the old/new dbs, and drop the old if the new is
        # okay.
        if clear:
            if not env.no_prompts:
                prompt = raw_input(
                    "\nReally for reals wipe out the %s database? Really (yes/no)?" % name
                )
                if prompt.lower() != "yes":
                    print "\nAborting!"
                    return False
            drop(name)
        system.sudo("mysql %s < %s" % (name, filename))


@task
def master_status():
    """
    Display the MySQL master status
    """
    out = run("SHOW MASTER STATUS;", show=False)
    m = re.search(r'(mysql-bin\.\d+)\s+(\d+)', out, re.MULTILINE)
    ret = None
    if m:
        ret = (m.group(1), m.group(2))
    print ret
    return ret
