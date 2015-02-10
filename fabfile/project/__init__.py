import os
from subprocess import check_output, check_call
from fabric.api import env, task, cd, settings
from fabric.contrib.files import exists
from .. import util, system
from .. contextmanagers import project  # , log_call, virtualenv

__all__ = [
    'create', 'install', 'remove', 'remove_templates',
    'git_push', 'get_git_remotes', 'create_user', 'pip'
]


@task
def remove():
    """
    Blow away the current project
    """
    if exists(env.virtualenv_path):
        system.sudo("rm -rf %s" % env.virtualenv_path)


@task
def remove_templates():
    """
    Remove any files we have deployed from templates
    """
    for template in util.get_templates().values():
        remote_path = template["remote_path"]
        if exists(remote_path):
            system.sudo("rm %s" % remote_path)


@task
def git_push(rev=None):
    """
    Push the local git repo to the remote hosts
    """

    # push either the specified revision, or the default GIT_BRANCH as
    # specified in settings.
    if rev is None:
        rev = env.git_branch

    # ensure the project path exists and is an initialiezd git repo.
    if not exists(env.project_root):
        raise Exception(
            "The project root is missing! Do you need to run the install() task?")
    with cd(env.project_root):
        system.run("git init")
        set_permissions()

    remotes = get_git_remotes()

    # deprecated; see function docstring
    # define_local_git_ssh()

    # Set up the remote host as a git remote in our local configuration
    #
    # WAT: By only executing this sequence if the host is not listed in the remotes,
    # deployments will break if we change either the user or project root.
    # Needs fixin.
    h = env.host_string
    if h not in remotes:
        util.print_command("git remote add %s %s@%s:%s" % (h, env.user, h, env.project_root))
        check_call(["git", "remote", "add", h, "%s@%s:%s" % (env.user, h, env.project_root)])
        remotes = get_git_remotes()

    # A little git jazz-hands here, to manage the push by first checking to see if
    # the default branch exists in the remote repository.
    pushed = False
    if rev == env.git_branch:
        # determine if the remote branch exists
        with cd(env.project_root):
            ret = system.run("git branch")
            if rev not in ret:
                util.print_command("git push %s %s" % (h, rev))
                check_call(["git", "push", h, rev])
                pushed = True

    # The first push must create the master branch, so we must only specify the rev,
    # not the source ref. Because git reasons...
    if not pushed:
        util.print_command("git push %s HEAD:%s" % (h, rev))
        check_call(["git", "push", h, "HEAD:%s" % rev])

    # ...but pushing into a branch on a remote that already exists will cause madness;
    # we must ensure the working tree is in sync with the newly-pushed ref.
    with cd(env.project_root):
        system.run("git checkout %s" % rev)
        system.run("git reset --hard")  # weeeeee!
        system.run("git submodule init")
        system.run("git submodule update")

        # fix up the permissions immediately after completing the push, so we don't
        # try to interact with files we cannot read or modify.
        set_permissions()


@task
def create():
    """
    (re)create a virtualenv for a python project deployment

    This function sets up the entire virtualenv, initializes the local git repo inside the project
    root, and pushes up the local branch.  If invoked when the local virtualenv already exists, it
    will prompt for confirmation before destorying its, unless NO_PROMPTS is True in your settings.
    """

    # Create virtualenv
    system.sudo("mkdir -p %s" % env.virtualenv_home)
    system.sudo("chown %s:staff %s" % (env.user, env.virtualenv_home))

    # this bit also evolved from the mezzanine original. Seriously, what a
    # great project.
    with cd(env.virtualenv_home):

        # remove the existing virtual environment and project root, if any.
        if exists(env.project_name):
            if not env.no_prompts:
                prompt = raw_input("\nVirtualenv exists: %s\nWould you like "
                                   "to replace it? (yes/no) " % env.project_name)
                if prompt.lower() != "yes":
                    print "\nAborting!"
                    return False
            remove()

        # create the new virtualenv and project root
        system.sudo("virtualenv %s" % env.project_name)
        system.sudo("mkdir -p %s" % env.project_root)
        set_permissions()

    with cd(env.project_root):

        # do the initial configuration of the git client, so that we can do our
        # push unmolested.
        if env.use_git:
            system.sudo(
                "su -l {0} -c \"git config --global user.email '{0}'\"".format(env.project_user))
            system.sudo(
                "su -l {0} -c \"git config --global user.name  '{0}'\"".format(env.project_user))
            system.sudo("su -l {0} -c \"git config --global receive.denyCurrentBranch ignore\"".format(
                env.project_user
            ))
            git_push()
        else:

            # WAT not sure I ever want to re-implement flat-file support, tbqh.
            raise NotImplementedError(
                "flat-file support not implemented at this time.")
            #root = os.path.dirname(os.path.abspath(__file__))
            #system.sudo("mkdir -p %s" % env.project_root)
            # for target in env.upload_targets:
            #    put("%s/%s" %
            #        (root, target), env.project_root, use_sudo=True, mirror_local_mode=True)


@task
def install():
    """
    Create the python virtualenv and deployment directories if necessary

    A generic installation task that should be run at least once when deploying a new project,
    since it covers a bunch of stuff that will be common to any python application deployment.
    """

    create_user()
    if not exists(env.virtualenv_home) or not exists(env.project_root):
        create()
        install_dependencies()
        return True
    return False


def set_permissions():
    """
    Ensure that the project entire virtualenv is owned by the project user,
    that all directories are 2775, and that all files are writable by the group.

    This allows the privileged fabric ssh user to modify these files during
    deployment, but keeps everything nicely isolated when accessed from inside
    the running application.
    """

    system.sudo("chown -R %s:%s %s" % (env.project_user, env.project_group, env.virtualenv_path))
    system.sudo("find %s -type d -exec chmod 2775 {} \\;" % env.virtualenv_path)
    system.sudo("find %s -type f -exec chmod g+rw {} \\;" % env.virtualenv_path)


def define_local_git_ssh():
    """
    Configure git to execute ssh with the corrrect identity file.

    WAT: This is likely deprecated now that we correctly honor fab's command-line overrides,
    so we should consider this for removal.
    """
    if not env.key_filename:
        return

    sh = './fabric_ssh.sh'

    # skip host IP checking, but only in staging.
    ssh_opts = ""
    if env.environment == 'staging':
        ssh_opts = '-oCheckHostIP=no'

    with open(sh, 'w') as f:
        f.write('#!/bin/sh\n')
        f.write('ssh -i %s %s $*' % (env.key_filename, ssh_opts))
    os.chmod(sh, 0755)
    os.environ.setdefault('GIT_SSH', sh)


def get_git_remotes():
    """
    Return a dict of remotes in the current (local) git repo.
    """
    remotes = {}
    for line in check_output(["git", "remote", "-v"]).split("\n"):
        # Sample output:
        #    foo.org     fabric@foo.org:/websites/foo/project.git (push)
        if line:
            (name, url, op) = line.split()
            if op == "(push)":
                remotes[name] = url
    return remotes


def create_user():
    """
    (re)create the user and group under which the project should run

    The project user is limited -- it should not have sudo access, nor should
    it be a member of the staff group.
    """

    # warnings only, since we accept more than the 0 exit status.
    with settings(warn_only=True):
        system.sudo("groupadd -f %s" % env.project_group)
        result = system.sudo(
            "useradd -g {1} -m -d /home/{0} -s /bin/bash {0}".format(
                env.project_user,
                env.project_group
            )
        )
    if result.return_code not in [0, 9]:
        print result
        raise SystemExit()

    # We place the fabric ssh user in the project group, because the
    # fabric user needs to be able to modify files owned by the user.
    system.sudo("usermod -a -G {1} {0}".format(env.fabric_user, env.project_group))


@task
def pip(packages):
    """
    Installs one or more Python packages within the virtual environment.
    """
    return system.sudo("pip install %s" % packages)


@task
def install_dependencies():
    """
    Install any missing or updated python modules listed in PIP_REQUIREMENTS_PATH
    """

    with project(env):
        for p in getattr(env, 'pip_requirements_path', []):

            # skip any requirements file that doesn't exist on the remote host. This lets us
            # ignore cotton's default requirements, if they're listed in the env.
            #
            # WAT Should we print a warning here? meh.
            fn = env.project_root + '/' + p
            if exists(fn):
                pip("-r %s" % fn)
