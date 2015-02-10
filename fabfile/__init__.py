# fabfile.py
#   -- fabric deployment tasks
#
import sys
import os
from fabric.api import env
import system

__all__ = [
    'set_env', 'system', 'mysql', 'postfix', 'iojs'
]


def set_env(settings_module):
    """
    Configure fabric's shared environment with values loaded from the settings module.

    This should be invoked once at startup to bootstrap the shared env; refer to the
    __main__ section at the bottom of this file for an example.
    """

    # load the specified module
    conf = __import__(settings_module, globals(), locals(), [], 0)

    # if the -u flag was not specified when fabric was invoked, we will execute all tasks
    # as the SSH_USER from the settings module.  We have to check for this one manually,
    # since by default fabric will set env.user to the EUID user, if -u is not
    # specified.
    if '-u' not in sys.argv:
        env.user = conf.SSH_USER

    # Step through all the variables in the settings module that are ALL_UPPERCASE, and
    # set corresponding all_lowercase attributes on the env object, but only if the attribute
    # doesn't already exist. Thus we honor any overrides specified in the fab
    # command line.
    for k in [k for k in conf.__dict__.keys() if k.upper() == k]:
        v = getattr(env, k.lower(), None)
        if not v:
            setattr(env, k.lower(), getattr(conf, k, None))

    env.all_admin_ips = ','.join(env.admin_ips)

    # Some sugar to disambiguate references to 'user' in the templates
    env.fabric_user = env.user


if __name__ == '__main__':

    # don't allow direct invocation of this script. use the force^Wfab, Luke!
    if sys.argv[0].split(os.sep)[-1] != 'fab':
        raise Exception("Please run 'fab' to execute fabric tasks.")

    # import settings from the local directory; this can be extended by setting the environment
    # variable COTTON_TARGET; refer to cotton/settings/__init__.py.
    set_env('settings')
