# -*- coding:utf-8 -*-

import os
from .vdev import VDev
from .disk import Disk

class SpaMgr(object):
    def __init__(self):
        self.disks = {}
        self.root_vdevs = {}
        self.spas_by_guid = {}
        self.spas_by_name = {}
        self.scan()
    
    def ls(self):
        self.scan()
        for name in self.spas_by_name:
            for spa in self.spas_by_name[name]:
                print('-' * 80)
                print('%s[%x]: ' % (name, spa.pool_guid))
                print('-' * 80)
                spa.dump_topo(indent=1)
                print('-' * 80)
                print('')
    
    def lookup(self, name):
        self.scan()
        if name not in self.spas_by_name:
            return None
        
        spas = self.spas_by_name[name]
        if len(spas) > 1:
            raise Exception('There are more than one pool with name %s: %s' % (
                name, str([spa.pool_guid for spa in spas])
            ))
        
        return spas[0]
    
    def scan(self):
        devs = []
        for dev in self._ls_devs():
            if dev not in self.disks:
                disk = Disk(dev)
                is_zfs = disk.is_zfs
                self.disks[dev] = is_zfs
                self.disks[disk.path] = is_zfs
                if is_zfs:
                    devs.append(disk.path)
        
        if devs:
            VDev.parse(devs, root_vdevs=self.root_vdevs)
            for pool_guid in self.root_vdevs:
                rvd = self.root_vdevs[pool_guid]
                if pool_guid not in self.spas_by_guid:
                    spa = self.spas_by_guid[pool_guid] = Spa(
                        rvd['name'], pool_guid, rvd)
                    if spa.name not in self.spas_by_name:
                        self.spas_by_name[spa.name] = []
                    self.spas_by_name[spa.name].append(spa)
                else:
                    spa = self.spas_by_name[spa.name]
                    assert(spa.root_vdev == rvd)
                    assert(spa.name == rvd['name'])
    
    def _ls_devs(self):
        return [ os.path.join('/dev/' + d)
                for d in os.listdir('/dev') if d.startswith('sd')
            ]

class Spa(object):
    def __init__(self, name, pool_guid, root_vdev):
        self.name = name
        self.pool_guid = pool_guid
        self.root_vdev = root_vdev
        self.uberblock = None
    
    def load_uberblock(self):
        ubs = {}
        leaves = self.root_vdev.get_leaves()
        for leaf in leaves:
            ubs[leaf['path']] = leaf.inst.select_uberblock()
        
        best_ub,xchg = None,0
        for path in ubs:
            ub = ubs[path]
            if not best_ub:
                best_ub = ub
            else:
                if ub.ub_txg > best_ub.ub_txg:
                    xchg += 1
                    best_ub = ub
        
        self.uberblock = best_ub
        
        assert(best_ub)
        if xchg > 0:
            raise Exception('Not all disk with highest txg')
        
        return True
    
    def open(self):
        if not self.root_vdev.open():
            return False
        
        if not self.load_uberblock():
            return False
        
        return True
    
    def close(self):
        self.root_vdev.close()
    
    def dump_topo(self, indent=0, tab=2):
        self.dump_child(vdev=self.root_vdev, indent=indent, tab=tab)
    
    def dump_child(self, vdev, indent=0, tab=2):
        for child in vdev['child']:
            if child.is_leaf:
                print('%*s[%d]%s' % (indent*tab, ' ',
                    child['id'], child['path']))
            else:
                print('%*s[%d]%s' % (indent*tab, '',
                    child['id'], child['type']))
                self.dump_child(child, indent=indent+1, tab=tab)
