from fabric.api import task  # , env

# import the fabric tasks and templates from cotton
import cotton.fabfile as cotton

# load application-specific settings from this module
cotton.set_fabric_env('cotton_settings')

# Add fabric tasks unique to your application deployment here.  The ship() task is an example of a
# minimal deployment. If you do nothing else, you need to push your your code to the remote host(s),
# and update the virtual environments with any changes in your python dependencies list.
#
# If you import env from frabric.api, you can access the entirety of the fabric shared environment,
# including all of the configuration loaded at runtime from both the cotton defaults and your local
# cotton_settings.py file.
#


@task
def ship():
    """
    Deploy the current branch to production
    """
    cotton.git_push()
    cotton.install_python_dependencies()
