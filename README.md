[![Stories in Accepted](https://badge.waffle.io/evilchili/cotton.png?label=accepted&title=Accepted+Issues)](https://waffle.io/evilchili/cotton)

# Cotton
**Lightweight Automated Deployment Toolkit For Debian/Ubuntu**

## Overview

Cotton is a python library that aims to radically simplify automated configuration management for Continuous Delivery environments. Cotton is built upon Fabric, and uses Fabric's concept of *tasks* to provide all the tools necessary to bootstrap new hosts, configure system packages, and deploy full application stacks.

Cotton is designed first for python applications being deployed to Debian systems, but is easy to extend for other environments; see for example the `cotton.fabfile.iojs` submodule.


## Rationale

Cotton is *narrowly scoped* -- it is not intended to provide a generic solution for automated configuration management across multiple platforms. There are [several](http://cloudinit.readthedocs.org/en/latest/index.html) [excellent](http://www.ansible.com/home) [solutions](https://www.chef.io/chef/) in that space already. 

Instead, Cotton aims to provide the smallest possible set of tools that can:
* bootstrap freshly-deployed Debian or Ubuntu systems with commonly-required packages for development and deployment;
* deploy, redeploy and heal python application stacks, and
* remain intelligible to developers with no knowledge of declarative configuration management.

Also, unlike full-blown configuration management packages, cotton makes no philosophical demands on how you use it -- you can ignore the entire `system` module, for example, and only use the `project` module for python application deployments. You can selectively enable or disable entire sets of features, simply by choosing what modules to import into your config.  This flexibility is a direct result of leveraging fabric's excellent namespacing features.


## Quickstart

To add cotton to an existing project as a submodule:

1. `pip install fabric`
2. create a `/build` directory in your application root
3. `git submodule add https://github.com/evilchili/cotton build/cotton`
4. copy cotton's `/build-template/*` into your `/build` directory
5. edit `/build/cotton_settings.py` to configure cotton for your application deployment

To test your config, switch to your `/build` directory and run:
```
% fab -l
```

This should list the tasks that available to run in the default config, which includes the `system` and `project` modules, 
as well as the example `ship` task from the fabfile:
```
Available commands:

    ship                         Deploy the current branch to production
    project.create               (re)create a virtualenv for a python project deployment
    project.git_push             Push the local git repo to the remote hosts
    project.install              Create the python virtualenv and deployment directories if necessary
    project.pip                  Installs one or more Python packages within the virtual environment.
    project.remove               Blow away the current project
    system.apt                   Installs one or more system packages via apt
    system.bootstrap             Meta-task that bootstraps the base system; must be run as root
    system.create_staff          Create any missing staff accounts
    system.ensure_running        Ensure all services listed in settings.ENSURE_RUNNING are running
    system.firewall              Configure a default firewall allowing inbound SSH from admin IPs
    system.install_dependencies  Install or update system dependencies listed in APT_REQUIREMENTS_PATH
    system.run                   Runs a shell comand on the remote server
    system.set_locale            Set the system locale
    system.set_timezone          Set the system timezone
    system.sudo                  Runs a command as sudo, unless the current user is root, in which case just run it
```

You can test that your SSH configuration is correct by executing a simple `run` task:

```
% fab system.run:"uptime"
```

This should result in output similar to the following:
```
[host1.local] Executing task 'system.run'

$ uptime ->

[host1.local] out:  16:37:22 up 1 day,  4:08,  1 user,  load average: 0.00, 0.01, 0.05
[host1.local] out:

Done.
Disconnecting from host1.local... done.
```

*Note: this will obviously get easier once I've released Cotton to PyPi -- chili*

## TBC...

