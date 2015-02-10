# cotton/settings.py
import os

# The local path to cotton -- used for locating and loading submodules, templates, etc.
COTTON_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

# import the default settings for submodules, if any
module_list = os.environ.get('COTTON_LIBS', 'system,project,postfix,mysql,iojs')
for module in module_list.split(','):
    try:
        exec("from %s import *" % module) in locals()
    except Exception as e:
        print "WARNING: Could not locate local settings for module '%s'" % module
