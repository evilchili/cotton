from fabric.api import cd, prefix  # , sudo as _sudo, run as _run, hide, task, get, put, settings
from contextlib import contextmanager
from functools import wraps
from fabric.colors import green


def log_call(func):
    """
    Pretty-print calls to functions.

    This is actually a decorator, not a context manager, but whatever.
    """
    @wraps(func)
    def logged(*args, **kawrgs):
        header = "-" * len(func.__name__)
        print green("\n".join([header, func.__name__, header]), bold=True)
        return func(*args, **kawrgs)
    return logged


@contextmanager
def virtualenv(env):
    """
    Runs commands within the project's virtualenv.
    """
    with cd(env.virtualenv_path):
        with prefix("source %s/bin/activate" % env.virtualenv_path):
            yield


@contextmanager
def project(env):
    """
    Runs commands within the project's directory.
    """
    with virtualenv(env):
        with cd(env.project_root):
            yield
