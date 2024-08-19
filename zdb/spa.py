# -*- coding:utf-8 -*-

from .dmu import *
from .vdev import *
from .zctypes import *
from .utils import MagicError

class Spa(object):
    def __init__(self, root_vdev):
        self.rvd = root_vdev
        self.name = root_vdev.name
        self.uberblock = None
        self.opened = False
    
    def open(self, do_open=True):
        self.uberblock = self.sel_ub()
        assert(self.uberblock)
        
        self.reader = BlkPtrReader(self.rvd)
        self.rootbp = self.uberblock.ub_rootbp
        
        if do_open:
            self._open_impl()
        
        return True
    
    def _open_impl(self):
        if self.opened:
            return
        
        self.mos = ObjSet(spa=self, blkptr=self.rootbp)
        self.rdir = self.mos.get(1, type=Zap)
        
        obj = self.rdir.lookup('root_dataset', fmt='num')[0]
        self.rdd = self.mos.get(obj, type=DslDir)
        self.rds = self.rdd.get_ds(self.rdd.phys.dd_head_dataset_obj)
        
        # TODO: ...
        
        self.opened = True
    
    def sel_ub(self):
        ubs = []
        for vd in self.rvd.leaves:
            ub = self.sel_ub_from_vd(vd)
            assert(ub)
            ubs.append(ub)
        
        ubs.sort(key = lambda ub : ub.ub_txg)
        return ubs[-1]
    
    @classmethod
    def sel_ub_from_vd(cls, vd):
        # TODO: Only read uberblocks in Label 0 but skip 1~3
        raw = memoryview(vd.disk.read_uberblock(label_index=0))
        
        ubs,pos,ub_sz = [],0,cls.ub_size(vd)
        while pos+ub_sz <= len(raw):
            try:
                ubs.append(UberBlock(raw[pos:pos+ub_sz]))
            except MagicError:
                pass
            pos += ub_sz
        
        ubs.sort(key = lambda ub : ub.ub_txg)
        return ubs[-1]
    
    @classmethod
    def ub_size(cls, vd):
        UBERBLOCK_SHIFT = 10 # 1K
        MAX_UBERBLOCK_SHIFT = 13 # 8K
        shift = min(max(UBERBLOCK_SHIFT, vd.top.ashift), MAX_UBERBLOCK_SHIFT)
        return 1 << shift

class SpaManager(object):
    def __init__(self, disks=None):
        self.vdmgr = VDevManager()
        self.spas = {}
        self.vdmgr.scan(disks=disks)
    
    def ls(self):
        self.vdmgr.ls()
    
    @classmethod
    def split_path(cls, path):
        return [i for i in path.split('/') if i]
    
    def open_pool(self, pool, do_open=True):
        components = self.split_path(pool)
        pool_name = components[0]
        
        if pool_name in self.spas:
            spa = self.spas[pool_name]
        else:
            rvd = self.vdmgr.lookup(pool_name)
            if not rvd or not rvd.open():
                return None
            spa = Spa(root_vdev=rvd)
            self.spas[pool_name] = spa
        
        if spa.open(do_open=do_open):
            return spa
        else:
            return None
    
    def open_ds(self, name):
        components = self.split_path(name)
        spa = self.open_pool(components[0])
        if not spa:
            return None
        dd = spa.rdd
        
        components = components[1:]
        while components:
            comp = components[0]
            components = components[1:]
            dd = dd.get_dd_by_name(comp)
        
        return dd.get_ds(dd.phys.dd_head_dataset_obj)
