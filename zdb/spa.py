# -*- coding:utf-8 -*-

from .vdev import *
from .zctypes import *
from .utils import MagicError

class Spa(object):
    def __init__(self, root_vdev):
        self.rvd = root_vdev
        self.name = root_vdev.name
        self.uberblock = None
    
    def open(self):
        self.uberblock = self.sel_ub()
        assert(self.uberblock)
        return True
    
    def sel_ub(self):
        ubs = []
        for vd in self.rvd.leaves:
            ub = self.sel_ub_from_vd(vd)
            assert(ub)
            ubs.append(ub)
        
        ubs.sort(key = lambda ub : ub.ub_txg)
        return ubs[-1]
    
    def sel_ub_from_vd(self, vd):
        # TODO: Only read uberblocks in Label 0 but skip 1~3
        ub_off,ub_len = 128*1024,128*1024
        raw = memoryview(vd.disk.read(ub_off,ub_len))
        
        ubs,pos,ub_sz = [],0,self.ub_size(vd)
        while pos < ub_len:
            try:
                ubs.append(UberBlock(raw[pos:pos+ub_sz]))
            except MagicError:
                pass
            pos += ub_sz
        
        ubs.sort(key = lambda ub : ub.ub_txg)
        return ubs[-1]
    
    def ub_size(self, vd):
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
    
    def open_pool(self, pool):
        rvd = self.vdmgr.lookup(pool)
        if not rvd or not rvd.open():
            return None
        
        spa = Spa(root_vdev=rvd)
        if spa.open():
            return spa
        else:
            return None
