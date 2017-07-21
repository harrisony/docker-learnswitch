#!/usr/bin/env python
'''
Description:
Add opaqueData key/value pairs on Host and PortGroup:
   com.vmware.netoverlay.layer1              = 'learnswitch'   (host)
   com.vmware.net.learnswitch.enable         = '1'             (portgroup)

Example:
   ./learnswitch_cfg.py  192.168.1.150 VDS-6.5 192.168.1.148 add|remove
                         [vc_ip     ] [dvs_name           ] [host_ip    ] [add|remove]

This script is a modified version of net-learnswitch.py.
'''

# Description: Unit tests for dvs Opaque Channel.
# Group-dvs: required
# Number-ESXs: 1

from optparse import OptionParser
import os
import pwd
import re
import sys
import ssl
import time
import yaml

import pyVim
from pyVim.task import WaitForTask
from pyVmomi import Vim, Vmodl, SoapStubAdapter, VmomiSupport
import pyVmomi as pyVmomi
vim  = pyVmomi.vim
from pyVmomi.VmomiSupport import newestVersions
import pyVim.connect as connect

#DEBUG = True
DEBUG = False

###############################################################################
##
## CONFIG
##
vc_user = os.environ['vc_user']
vc_password = os.environ['vc_password']

dvpg_name_list = os.environ['dvpg_name_list'].split(',')
##
###############################################################################

service_instance = vc_ip = host_ip = action = dvs_name = None
action = 'add'

if len(sys.argv) >= 2:
	vc_ip = sys.argv[1]
if len(sys.argv) >= 3:
	dvs_name = sys.argv[2]
if len(sys.argv) >= 4:
	host_ip = sys.argv[3]
if len(sys.argv) >= 5:
	action = sys.argv[4]


def usage():
   print
   print "Usage:", sys.argv[0], "<vc> <dvs-name> <esx-ip> <add|remove>"
   print
   print 'Note: <esx-ip> MUST be an IP address, not a hostname or FQDN'
   print
   print '''
Description:
   Add opaqueData key/value pairs on Host and PortGroup:
   com.vmware.netoverlay.layer1              = 'learnswitch' (host)
   com.vmware.net.learnswitch.enable         = '1'           (portgroup)

Example:
   ./learnswitch_cfg.py 192.168.1.150 VDS-6.5 192.168.1.148 add
   ./learnswitch_cfg.py 192.168.1.150 VDS-6.5 192.168.1.148 remove
'''
   print
   sys.exit(0)

#############################################################################
#
# check all passed-in arguments are valid
#
if not vc_ip:
   usage()
if not dvs_name:
   print "ERROR: must specify dvs name"
   print
   usage()
if not re.search('^\d+\.\d+\.\d+\.\d+$', host_ip):
   print "ERROR: must specify a host IP address"
   print
   usage()
if action not in ('add', 'remove'):
   print "ERROR: must specify an action: add remove"
   print
   usage()

##############################################################################
#
# add opaqueData 'learnswitch' overlay to hostMor host
#
def edit_learnswitch_overlay(dvsManager, dvsUuid, hostMor):
   # Create a Selection Set
   sel_set = Vim.Dvs.HostMemberSelection()
   sel_set.SetDvsUuid(dvsUuid)
   sel_set.host = hostMor

   key = "com.vmware.netoverlay.layer1"
   val = 'learnswitch'

   #
   # return if key is already set
   #
   kvlist = get_opaque_data(dvsManager, sel_set)
   # [('com.vmware.netoverlay.layer1', 'learnswitch')]
   found = False
   if len(kvlist)>= 1:
      for k, v in kvlist:
         if k == key:
            if action == 'add':
               print 'INFO:', key, 'already exists with value:', v, \
                     'on host:', hostMor.name +'. No changes made.'
               return
            else:
               found = True

   if action == 'remove' and not found:
      print 'INFO:', key, 'does not exist on PG:',hostMor.name+\
            '. No changes made.'
      return

   data2 = Vim.Dvs.OpaqueData()
   data2.SetKey(key)
   val = VmomiSupport.binary(val)
   print 'INFO: Set:', key,'=',val, 'on host', hostMor.name
   data2.opaqueData = val

   # Create opaqueSpec for new API
   opaqueSpec2 = Vim.Dvs.OpaqueData.ConfigSpec()
   opaqueSpec2.SetOperation(action)
   opaqueSpec2.SetOpaqueData(data2)
   updateTask = dvsManager.UpdateOpaqueDataEx([sel_set], [opaqueSpec2], False)
   WaitForTask(updateTask)

##############################################################################
#
# read all OpaqueData configuration for objects selected
# by sel_set(Object Selection set)
#
def get_opaque_data(dvsManager,sel_set):
   keyval_list = []
   od_cfg_info_list = dvsManager.FetchOpaqueDataEx([sel_set], isRuntime=False)
   if DEBUG:
      print
      print '+'+'-'*78
      print '| get_opaque_data()'
      print '|', od_cfg_info_list
      print '+'+'-'*78
   for od_cfg_info in od_cfg_info_list:
      for od in od_cfg_info.opaqueData:
         _key = od.key
         _val = od.opaqueData
         if DEBUG:
            print '| _key, _val:', _key, _val
         keyval_list.append((_key, _val))
   if DEBUG:
      print '+'+'-'*78,'\n'
   return keyval_list

##############################################################################
#
# add opaqueData key/value to pgMor portgroup
#
def edit_pg_key_value(dvsManager, dvsUuid, pgMor, key, val):
   # Create a Selection Set
   sel_set = Vim.Dvs.DistributedVirtualPortgroupSelection()
   sel_set.SetDvsUuid(dvsUuid)
   sel_set.SetPortgroupKey(pgMor.key)

   #
   # return if key is already set
   #
   kvlist = get_opaque_data(dvsManager, sel_set)
   # [('com.vmware.net.learnswitch.enable', '1')]

   found = False
   if len(kvlist)>= 1:
      for k,v in kvlist:
         if k == key:
            if action == 'add':
               print 'INFO:', key, 'already exists with value:', v, \
                     'on PG:',pgMor.name+'. No changes made.'
               return
            else:
               found = True

   if action == 'remove' and not found:
      print 'INFO:', key, 'does not exist on PG:',pgMor.name+\
            '. No changes made.'
      return

   # add basic data for dvpg (no inheritance)
   data2 = Vim.Dvs.InheritedOpaqueData()
   data2.inherited = False
   data2.SetKey(key)
   bin_val = VmomiSupport.binary(val)
   print 'INFO: Set:', key,'=',bin_val, 'on PG:', pgMor.name
   data2.opaqueData = bin_val

   # Create opaqueSpec for new API
   opaqueSpec2 = Vim.Dvs.OpaqueData.ConfigSpec()
   opaqueSpec2.SetOperation(action)
   opaqueSpec2.SetOpaqueData(data2)
   updateTask = dvsManager.UpdateOpaqueDataEx([sel_set], [opaqueSpec2], False)
   WaitForTask(updateTask)

##############################################################################
#
# login to VC; set service_instance and return si.content
#
def get_vc_content():
    global service_instance
    """ function to get content object of given vc

    @param options cli options to this script
    @return vc content object
    """

    stub = SoapStubAdapter(host=vc_ip, port=443,
                           path="/sdk", version="vim.version.version8")
    service_instance = Vim.ServiceInstance("ServiceInstance", stub)
    ssl._create_default_https_context = ssl._create_unverified_context
    #service_instance = connect.SmartConnect(
    #          host=vc_ip, user=vc_user, pwd=vc_password, port=443)

    if not service_instance:
       print "serviceInstance not defined"
    content = service_instance.RetrieveContent()
    if not content:
       print "content not defined"
    content.sessionManager.Login(vc_user, vc_password)
    return content

##############################################################################
#
# return dvsMor matching dvs_name
#
def get_dvs_mor(dvs_name):
    content = get_vc_content()
    def get_dvs_mor_from_folder(dvs_name, folder):
        for entity in folder.childEntity:
            if isinstance(entity, vim.Datacenter):
                return get_dvs_mor_from_datacenter(dvs_name, entity)
            elif isinstance(entity, vim.Folder):
                return get_dvs_mor_from_folder(dvs_name, entity)

    def get_dvs_mor_from_datacenter(dvs_name, datacenter):
        for child in datacenter.networkFolder.childEntity:
            if isinstance(
                    child,
                    vim.dvs.VmwareDistributedVirtualSwitch):
                if child.name == dvs_name:
                    return child

    for entity in content.rootFolder.childEntity:
        if isinstance(entity, vim.Datacenter):
            dvs_mor = get_dvs_mor_from_datacenter(dvs_name, entity)
        elif isinstance(entity, vim.Folder):
            dvs_mor = get_dvs_mor_from_folder(dvs_name, entity)
        else:
            print("dvs has to be in a folder or a datacenter")
        if dvs_mor:
            return dvs_mor
    print 'ERROR: DVS %s not found'% dvs_name
    sys.exit(1)

##############################################################################
#
# return pgMor with port group name(dvpg_name) on dvs
#
def get_dvpg_mor(dvpg_name, dvs_name):
    vds_mor = get_dvs_mor(dvs_name)
    for pg in vds_mor.portgroup:
        if pg.name == dvpg_name:
            return pg

##############################################################################
#
# return hostMor with host_ip
#
def get_host_mor(ip):
    content = get_vc_content()
    search = content.searchIndex
    return search.FindByIp(None, ip, vmSearch=False)

##############################################################################
#
# main()
#
def main():
   content  = get_vc_content()
   dvs_mor = get_dvs_mor(dvs_name)
   hostMor = get_host_mor(host_ip)
   dvsManager = content.dvSwitchManager

   if action == 'add':
      # add/remove learnswitch overlay based on action
      edit_learnswitch_overlay(dvsManager, dvs_mor.uuid, hostMor)

   # Prefer setting a key across -all- objects before setting
   # the next key, even though this is slightly less efficient.
   # It makes troubleshooting slightly easier when setting of key fails.
   dvpgmor_list = []
   for dvpg_name in dvpg_name_list:
      dvpg_mor = get_dvpg_mor(dvpg_name, dvs_name)
      if dvpg_mor:
         dvpgmor_list.append(dvpg_mor)
      else:
         print 'ERROR:', 'PortGroup(%s:%s) not found' % (dvs_name,dvpg_name)
         sys.exit(1)

   # enable learnswitch
   for dvpg_mor in dvpgmor_list:
      edit_pg_key_value(dvsManager, dvs_mor.uuid, dvpg_mor,
                       "com.vmware.net.learnswitch.enable", '1')

   if action == 'remove':
      # add/remove learnswitch overlay based on action
      edit_learnswitch_overlay(dvsManager, dvs_mor.uuid, hostMor)

if __name__ == "__main__":
   main()
