from fabric.api import task  # , env

# import the preconfigured tasks that ship with cotton. Loading fabfile submodules
# here will expose their tasks to the fab command-line.
from cotton.fabfile import set_env, system, project

# load your custom settings from this module
set_env('cotton_settings')


# Add fabric tasks unique to your application deployment here.  The ship() task is an example of a
# minimal deployment. If you do nothing else, you need to push your your code to the remote host(s),
# and update the virtual environments with any changes in your python dependencies list.
#
# If you import env from fabric.api, you can access the entirety of the fabric shared environment,
# including all of the configuration loaded at runtime from both the cotton defaults and your local
# cotton_settings.py file.
#
# Remember that if you are using cotton to configure your base system as well as manage your
# application deployments, you'll want to run the system.bootstrap() task before deploying
# your application for the first time:
#
# fab system.bootstrap
#
# Note that if you choose not to use cotton's system module to manage your server configs,
# you'll need to make sure the packages listed in requirements/apt.txt are present.
#
@task
def ship():
    """
    Deploy the current branch to production
    """
    project.git_push()
    project.install_dependencies()
