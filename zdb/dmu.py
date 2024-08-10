# -*- coding:utf-8 -*-

from .compressor import Compressor

class BlkPtrReader(object):
    def __init__(self, root_vdev):
        self.rvd = root_vdev
        assert(self.rvd.opened)
    
    def read(self, blkptr, verify=False):
        assert(not blkptr.embed)
        # TODO: verify whether all copies are same
        
        compressor = Compressor.from_int(blkptr.compr)
        # TODO: what if read content not compressed?
        assert(compressor.supported)
        
        loc = blkptr.diskLocation()
        assert(len(loc['dva']) > 0)
        dva = loc['dva'][0]
        
        vd  = self.rvd.child[dva['vdev']]
        # TODO: how to read disk of raidz or other formats
        assert(vd.is_leaf() and vd.type == 'disk')
        
        raw = vd.disk.read(dva['offset'], dva['asize'])
        return compressor.decompress(raw, loc['lsize'])
