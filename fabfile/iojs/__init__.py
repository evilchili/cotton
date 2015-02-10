from fabric.api import env, task, put, cd
import requests
import os
from .. import util
from ..contextmanagers import project  # , log_call, virtualenv
from ..system import _run as run


@task
def install(version='latest', target='linux-x64'):
    """
    Install the specified io.js distribution into the project virtualenv.
    """

    if version is not 'latest' and version[0] != 'v':
        version = 'v' + version

    # retrieve the SHA256 sums list, which will helpfully tell us what distros
    # are available
    base_url = 'https://iojs.org/dist/' + version
    res = requests.get(base_url + '/SHASUMS256.txt')
    if not res.status_code == 200:
        res.raise_for_status()

    # s required distro; adjust to taste.
    target = '%s.tar.gz' % target

    # locate the shasum and the filename we need
    match = [l for l in res.text.split('\n') if target in l]
    if not match:
        raise ("Could not locate signature for target '%s'" % target)
    sha, fn = match[0].split()

    if os.path.exists(fn) and not util.check_shasum(fn, sha):
        os.remove(fn)

    # if the io.js archive doesn't already exist locally, download it.
    if not os.path.exists(fn):
        res = requests.get(base_url + '/' + fn, stream=True)
        with open(fn, 'wb') as f:
            for chunk in res.iter_content(chunk_size=4096):
                if chunk:
                    f.write(chunk)
                    f.flush()
    if not util.check_shasum(fn, sha):
        raise Exception(
            "Downloaded %s but the SHASUM does not match SHASUMS256.txt!")

    # create a temporary directory, if one does not already exist
    tmpdir = env.virtualenv_path + '/tmp'
    run('mkdir -p %s' % tmpdir)

    # upload the distro to the tmp dir, and extract it into the virtualenv path
    put(fn, tmpdir)
    with cd(env.virtualenv_path):
        run("tar -o --no-overwrite-dir --strip-components=1 -xaf %s/%s" % (tmpdir, fn))

        # clean up
        with cd(tmpdir):
            run("rm -f %s" % fn)


@task
def install_dependencies():
    """
    Install io.js modules listed in the npm_requirements_path members
    """
    with cd(env.virtualenv_path):
        reqs = ''
        for p in getattr(env, 'npm_requirements_path', []):
            fn = os.path.abspath(
                os.path.join(os.path.dirname(os.path.abspath(__file__)), p))
            if os.path.exists(fn):
                with open(fn, 'r') as f:
                    for pkg in f.read().split('\n'):
                        reqs = "%s %s" % (reqs, pkg.strip())
        if reqs:
            return npm(reqs)


@task
def npm(modules):
    """
    Installs one or more iojs modules using npm
    """
    with project(env):
        return run("npm install %s --save" % modules)
