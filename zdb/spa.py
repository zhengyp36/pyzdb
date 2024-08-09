# -*- coding:utf-8 -*-

from .vdev import *

class Spa(object):
    def __init__(self, root_vdev):
        self.rvd = root_vdev
    
    def open(self):
        return True
    
    def uberblock_size(self, vd):
        UBERBLOCK_SHIFT = 10 # 1K
        MAX_UBERBLOCK_SHIFT = 13 # 8K
        shift = min(max(UBERBLOCK_SHIFT, vd.top.ashift), MAX_UBERBLOCK_SHIFT)
        return 1 << shift

class SpaManager(object):
    def __init__(self, disks=None):
        self.vdmgr = VDevManager()
        self.vdmgr.scan(disks=disks)
    
    def open_pool(self, pool):
        rvd = self.vdmgr.lookup(pool)
        if not rvd or not rvd.open():
            return None
        
        spa = Spa(root_vdev=rvd)
        if spa.open():
            return spa
        else:
            return None
