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
    
    def open(self, do_open=True):
        self.uberblock = self.sel_ub()
        assert(self.uberblock)
        
        self.reader = BlkPtrReader(self.rvd)
        self.rootbp = self.uberblock.ub_rootbp
        self.prtmgr = DmuPrtMgr(self)
        
        if do_open:
            self._open_impl()
        
        return True
    
    def _open_impl(self):
        self.mos = ObjSet(self.prtmgr.uberblock, self.rootbp)
        self.objdir = self.mos.get(1, type=Zap)
        
        obj = self.objdir.lookup('root_dataset', fmt='num')[0]
        self.rdd = self.mos.get(obj, type=DslDir)
        self.rds = self.mos.get(self.rdd.dd_phys.dd_head_dataset_obj,
            type=DslDataSet)
        
        # TODO: ...
    
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
        self.vdmgr.scan(disks=disks)
    
    def ls(self):
        self.vdmgr.ls()
    
    def open_pool(self, pool, do_open=True):
        rvd = self.vdmgr.lookup(pool)
        if not rvd or not rvd.open():
            return None
        
        spa = Spa(root_vdev=rvd)
        if spa.open(do_open=do_open):
            return spa
        else:
            return None
