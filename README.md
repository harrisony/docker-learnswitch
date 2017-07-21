Docker image for ESXi Learnswitch
==================================
[![Docker Build Status](https://img.shields.io/docker/build/harrisony/esxi-learnswitch.svg?style=flat-square)](https://hub.docker.com/r/harrisony/esxi-learnswitch/)

totally unlegit docker image of the python script accompanying the [ESXi learnswitch](https://labs.vmware.com/flings/learnswitch)

Likely breaks the VMware technology preview license...plz don't hate me, I like your [turtles](https://twitter.com/VMwareTurtles)

Usage
------
    docker pull harrisony/docker-learnswitch
    docker run -e vc_user=Administrator@vsphere.local -e vc_password=VMware1! -e dvpg_name_list=DVPG-Nested-ESXi-Workload-1,DVPG-Nested-ESXi-Workload-2
