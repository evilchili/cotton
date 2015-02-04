[![Stories in Accepted](https://badge.waffle.io/evilchili/cotton.png?label=accepted&title=Accepted+Issues)](https://waffle.io/evilchili/cotton)

# Cotton
**Lightweight Automated Deployment Toolkit For Debian/Ubuntu**

## Overview

Cotton is a python library that aims to radically simplify automated configuration management for Continuous Delivery environments. Cotton is built upon Fabric, and uses Fabric's concept of *tasks* to provide all the tools necessary to bootstrap new hosts, configure system packages, and deploy full application stacks.

Cotton is designed first for python applications being deployed to Debian systems, but is easy to extend for other environments.


## Rationale

Cotton is *narrowly scoped* -- it is not intended to provide a generic solution for automated configuration management across multiple platforms. There are [several](http://cloudinit.readthedocs.org/en/latest/index.html) [excellent](http://www.ansible.com/home) [solutions](https://www.chef.io/chef/) in that space already. 

Instead, Cotton aims to provide the smallest possible set of tools that can:
* bootstrap freshly-deployed Debian or Ubuntu systems with commonly-required packages for development and deployment;
* deploy, redeploy and heal python application stacks, and
* remain intelligible to developers with no knowledge of declarative configuration management.

## Quickstart

To add cotton to an existing project as a submodule:

1. `pip install fabric`
2. create a `/build` directory in your application root
3. `git submodule add https://github.com/evilchili/cotton build/cotton`
4. copy cotton's `/build-template/*` into your `/build` directory
5. edit `/build/cotton_settings.py` to configure cotton for your application deployment

To test your config, switch to your `/build` directory and run:
```
% fab cotton.run:"uptime"
```

This should result in output similar to the following:
```
[host1.local] Executing task 'cotton.run'

$ uptime ->

[host1.local] out:  16:37:22 up 1 day,  4:08,  1 user,  load average: 0.00, 0.01, 0.05
[host1.local] out:

Done.
Disconnecting from host1.local... done.
```

*Note: this will obviously get easier once I've released Cotton to PyPi -- chili*

## TBC...

