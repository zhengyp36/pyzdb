# -*- coding:utf-8 -*-

from .disk import Disk

class VDev(object):
    def __init__(self, parent=None, type=None):
        self.desc = {}
        self.desc['type'] = type
        self.parent = parent
        self.inst = None
        
        if parent is None:
            assert(type == 'root')
            self.top = None
        elif parent.top is None:
            assert(parent.is_root)
            self.top = self
        else:
            self.top = parent.top
    
    def get_root(self):
        if self.is_root:
            return self
        elif self.is_top:
            return self.parent
        else:
            return self.top.parent
    
    def get_top(self):
        if self.is_root:
            return None
        elif self.is_top:
            return self
        else:
            return self.top
    
    @property
    def opened(self):
        rvd = self.get_root()
        return 'opened' in rvd.desc and rvd.desc['opened']
    
    def open(self):
        if self.is_leaf:
            return self.open_leaf()
        
        for child in self.desc['child']:
            if child is None:
                return False
            
            if not child.open():
                return False
        
        if self.is_root:
            self.desc['opened'] = True
        return True
    
    def close(self):
        if self.is_leaf:
            return self.close_leaf()
        else:
            for child in self.desc['child']:
                child.close()
        
        if self.is_root:
            self.desc['opened'] = False
    
    def open_leaf(self):
        if not self.inst:
            self.inst = Disk(self.desc['path'])
            assert(self.inst)
            assert(self.inst.is_zfs)
        else:
            assert(isinstance(self.inst, Disk))
        return True
    
    def close_leaf(self):
        if self.inst:
            self.inst = None
    
    def __getitem__(self, key):
        if key not in self.desc:
            raise KeyError("'%s' not found in the desc" % key)
        return self.desc[key]
    
    @property
    def is_top(self):
        return self.top == self
    
    @property
    def is_root(self):
        return self.desc['type'] == 'root'
    
    @property
    def is_leaf(self):
        return  'children' not in self.desc
    
    @property
    def children(self):
        if self.is_leaf:
            return None
        else:
            return self.desc['children']
    
    @property
    def ready_children(self):
        if self.is_leaf:
            return None
        else:
            return self.desc['children'] - self.desc['child'].count(None)
    
    @property
    def ready(self):
        if self.is_leaf:
            return self.desc['ready']
        else:
            # TODO: how to tell whether all children are ready?
            return self.children == self.ready_children
    
    def init_children(self, children):
        assert(children > 0)
        self.desc['children'] = children
        self.desc['child'] = [None] * children
    
    def add_child(self, nvp):
        id = nvp['id']
        assert(id >= 0 and
            id < self.desc['children'] and
            self.desc['child'][id] is None)
        
        vd = self.desc['child'][id] = type(self)(parent=self, type=nvp['type'])
        vd.desc['guid'] = nvp['guid']
        vd.desc['id'] = id
        
        if 'path' in nvp:
            vd.desc['path'] = nvp['path']
        
        if 'children' in nvp:
            vd.init_children(len(nvp['children']))
            for child in nvp['children']:
                vd.add_child(child)
        
        if vd.is_leaf:
            vd.desc['ready'] = False
        
        return vd
    
    def mark_leaf_ready(self, guid):
        if self.is_leaf:
            if self.desc['guid'] == guid:
                assert(not self.desc['ready'])
                self.desc['ready'] = True
                return True
            else:
                return False
        else:
            for child in self.desc['child']:
                if child and child.mark_leaf_ready(guid):
                    return True
            return False
    
    def dump(self, indent=0, info=None):
        vdev_keys = [ 'type', 'id', 'guid', 'path', 'ready' ]
        keylen = max([len(k) for k in vdev_keys] + [len('is_top')])
        
        tab = 2 * ' '
        line = '-' * (80 - indent * len(tab))
        enterLine = '<' * (80 - indent * len(tab))
        exitLine = '>' * (80 - indent * len(tab))
        
        if info is None:
            info = []
        append = lambda msg : info.append(indent * tab + msg)
        
        append(line)
        if self.is_top:
            append('%-*s : %s' % (keylen, 'is_top', str(True)))
        
        for key in vdev_keys:
            if key in self.desc:
                append('%-*s : %s' % (keylen, key, str(self.desc[key])))
        if not self.is_leaf:
            for child in self.desc['child']:
                append(enterLine)
                if child:
                    child.dump(indent=indent+1, info=info)
                else:
                    append('missing the child ...')
                append(exitLine)
        append(line)
        
        if indent == 0:
            print('\n'.join(info))
    
    def add_top_child(self, nvp):
        tvd = self.add_child(nvp)
        assert(tvd.children == tvd.ready_children)
    
    @classmethod
    def make_root_vdev(cls, nvp):
        rvd = cls(type='root')
        
        rvd.desc['guid'] = nvp['pool_guid']
        rvd.desc['name'] = nvp['name']
        rvd.desc['pool_guid'] = nvp['pool_guid']
        
        rvd.init_children(nvp['vdev_children'])
        rvd.add_top_child(nvp['vdev_tree'])
        
        return rvd
    
    @classmethod
    def parse(cls, disk_list):
        root_vdevs = {}
        
        disks_saved = set()
        for path in disk_list:
            if path in disks_saved:
                continue
            disks_saved.add(path)
            
            disk = Disk(path)
            if disk.path != path:
                if disk.path in disks_saved:
                    continue
                disks_saved.add(disk.path)
            
            nvp = disk.pickup_label_nvpairs()
            if not nvp:
                continue
            
            if nvp['pool_guid'] not in root_vdevs:
                root_vdevs[nvp['pool_guid']] = cls.make_root_vdev(nvp)
            else:
                root_vdevs[nvp['pool_guid']].add_top_child(nvp['vdev_tree'])
            
            marked = root_vdevs[nvp['pool_guid']].mark_leaf_ready(nvp['guid'])
            if not marked:
                root_vdevs[nvp['pool_guid']].dump()
            assert(marked)
        
        return root_vdevs
