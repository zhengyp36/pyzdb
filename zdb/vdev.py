# -*- coding:utf-8 -*-

import os
from .disk import *
from .nvlist import *

class VDevManager(object):
    def __init__(self):
        self.root_vdevs = {}
        self.pool_names = {}
    
    def scan(self, disks=None):
        if not disks:
            devs = [ os.path.join('/dev',d)
                for d in os.listdir('/dev') if d.startswith('sd') ]
        else:
            devs = disks[:]
        
        # TODO: need read other labels if failed
        disk_min_size = 256*1024 * 4 + 3.5 * 1024 * 1024
        label_start, label_length = 16*1024, 112*1024
        
        for dev in devs:
            disk = Disk(dev)
            if disk.size.size <= disk_min_size:
                continue
            
            raw_data = disk.read(label_start, label_length)
            try:
                nvlist = NVList.from_bytes(raw_data)
            except AssertionError:
                continue
            
            rvd = VDev.make(nvlist, root_vdevs=self.root_vdevs)
            if not rvd:
                print('Add disk %s error.' % dev)
        
        for guid in self.root_vdevs:
            rvd = self.root_vdevs[guid]
            if rvd.name not in self.pool_names:
                self.pool_names[rvd.name] = set()
            self.pool_names[rvd.name].add(rvd.guid)
    
    def lookup(self, key):
        if key in self.root_vdevs:
            return self.root_vdevs[key]
        else:
            if key in self.pool_names:
                guids = self.pool_names[key]
                if len(guids) > 1:
                    print("There are more than one pool with name '%s'" % key)
                    print("Their guids are %s" % str(guids))
                    return None
                else:
                    return self.root_vdevs[list(guids)[0]]
            else:
                return None
    
    def ls(self):
        for guid in self.root_vdevs:
            rvd = self.root_vdevs[guid]
            rvd.dump_topo()
            print('')

class VDev(object):
    @classmethod
    def make(cls, nvlist, root_vdevs=None):
        # check whether nvlist is valid
        NVLIST_KEYS = [ 'name', 'pool_guid', 'vdev_tree', 'vdev_children' ]
        for key in NVLIST_KEYS:
            if key not in nvlist:
                return None
        
        if root_vdevs is None:
            root_vdevs = {}
        
        if nvlist['pool_guid'] not in root_vdevs:
            root_vdevs[nvlist['pool_guid']] = cls(nvlist)
        rvd = root_vdevs[nvlist['pool_guid']]
        
        top_id = nvlist['vdev_tree']['id']
        assert(top_id >= 0 and top_id < len(rvd.child))
        if not rvd.child[top_id]:
            rvd.add_child(nvlist['vdev_tree'])
        
        return rvd
    
    def __init__(self, nvlist, parent=None):
        self.parent = parent
        self.ashift = 0
        self.disk = None
        self.leaves = set()
        
        if parent is None:
            self.guid = nvlist['pool_guid']
            self.id = -1
            self.child = [None] * nvlist['vdev_children']
            self.type = 'root'
            self.name = nvlist['name'] # Only for root-vdev
        else:
            self.guid = nvlist['guid']
            self.id = nvlist['id']
            if 'children' in nvlist:
                self.child = [None] * len(nvlist['children'])
            else:
                self.child = []
            self.type = nvlist['type']
        
        if parent is None:
            self.top = None
        elif parent.parent is None:
            self.top = self
            self.ashift = nvlist['ashift']
        else:
            assert(parent.top)
            self.top = parent.top
        
        if len(self.child) == 0:
            self.path = nvlist['path']
        else:
            self.path = ''
    
    def add_child(self, nvlist):
        cvd = self.child[nvlist['id']] = type(self)(nvlist, parent=self)
        if len(cvd.child) != 0:
            for sub_nvl in nvlist['children']:
                cvd.add_child(sub_nvl)
    
    def dump_topo(self, indent=0, tab=2*' ', output=None):
        if output is None:
            lines = []
        else:
            lines = output
        
        if self.is_root():
            lines.append(indent*tab + '%s[GUID=%s]' % (
                self.name, hex(self.guid).strip('L')
            ))
        else:
            lines.append(indent*tab + '<%s>[%d]%s' % (
                self.type, self.id, self.path
            ))
        
        for cvd in self.child:
            cvd.dump_topo(indent=indent+1, tab=tab, output=lines)
        
        if output is None:
            print('\n'.join(lines))
    
    def verify(self, only_for_root=False):
        if only_for_root and not self.is_root():
            return
        
        if self.is_root():
            rvd = self
        else:
            rvd = self.top.parent
        
        ashift = 0
        for leaf in self.leaves:
            assert(leaf.top.ashift > 0)
            assert(ashift == 0 or leaf.top.ashift == ashift)
            ashift = leaf.top.ashift
    
    def open(self):
        if self._open():
            self.verify(only_for_root=True)
            return True
        else:
            self.close()
            return False
    
    def _open(self):
        if self.is_leaf():
            return self.open_leaf()
        
        for child in self.child:
            if not child:
                return False
            elif not child._open():
                return False
        
        return True
    
    def open_leaf(self):
        if self.disk:
            return True
        
        assert(self.path)
        self.disk = Disk(self.path)
        if self.disk:
            self.record_leaf()
            return True
        
        return False
    
    def record_leaf(self):
        if self.is_leaf():
            parent = self.parent
            while parent:
                parent.leaves.add(self)
                parent = parent.parent
    
    def close(self):
        for child in self.child:
            if child:
                child.close()
        self.disk = None
    
    def is_top(self):
        return self == self.top
    
    def is_root(self):
        return self.parent is None
    
    def is_leaf(self):
        return len(self.child) == 0
