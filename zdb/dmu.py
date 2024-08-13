# -*- coding:utf-8 -*-

from .zctypes import *
from .utils import *
from .compressor import Compressor

class BlkPtrReader(object):
    def __init__(self, root_vdev):
        self.rvd = root_vdev
        assert(self.rvd.opened)
    
    def read(self, blkptr, verify=False):
        if blkptr.is_hole:
            raise HoleError(type(self))
        
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

class DmuPrt(object):
    '''DMU-Parent'''
    DESC_TABLE = set([
        'uberblock',
        'os->mdn',
        'os->dn',
    ])
    
    def __init__(self, spa, desc, parent, detail=None):
        assert(desc in self.DESC_TABLE)
        self.spa    = spa
        self.desc   = desc
        self.parent = parent
        self.detail = detail
    
    def __str__(self):
        return '<%s>%s:%s' % (self.spa.name, self.desc, repr(self.parent))
    
    def equal(self, other):
        return (self.spa == other.spa and self.desc == other.desc and
            self.parent == other.parent and self.detail == other.detail)

class DmuPrtMgr(object):
    '''DMU-Parent-Manger'''
    def __init__(self, spa):
        self.spa = spa
        self.init_special()
    
    def init_special(self):
        self.specials = {
            'uberblock' : DmuPrt(self.spa, 'uberblock', self.spa.uberblock),
        }
        
        for desc in self.specials:
            setattr(self, desc, self.specials[desc])
    
    def get(self, desc, parent, detail=None):
        obj = DmuPrt(self.spa, desc, parent, detail=detail)
        if desc not in self.specials:
            return obj
        else:
            assert(obj.equal(self.specials[desc]))
            return self.specials[desc]

class ObjSet(object):
    def __init__(self, dmup, blkptr):
        self.dmup = dmup
        self.phys = ObjSetPhys(self.dmup.spa.reader.read(blkptr))
        self.blkptr = blkptr
        self.meta_dn = DNode(
            dmup.spa.prtmgr.get('os->mdn',self),
            self.phys.os_meta_dnode
        )
    
    def get(self, id, type=None):
        if type is None:
            type = DNode
            detail = None
        else:
            assert(issubclass(type,DNode))
            detail = type.__name__
        
        dnsz = DNodePhys.sizeof()
        assert(id > 0)
        assert(dnsz == 512)
        
        data = self.meta_dn.read(id * dnsz, dnsz)
        return type(
            self.dmup.spa.prtmgr.get('os->dn',self,detail=detail),
            DNodePhys(data)
        )

class DNode(object):
    def __init__(self, dmup, phys):
        self.dmup = dmup
        self.phys = phys
    
    def read(self, offset, length):
        blksz = self.phys.blksz
        start = curr = offset // blksz
        end   = (offset + length - 1 + blksz - 1) // blksz
        
        mv_ret = memoryview(bytearray(blksz * (end - start + 1)))
        while curr <= end:
            blk = memoryview(self.read_block(curr))
            mv_ret[(curr-start)*blksz:(curr-start+1)*blksz] = blk
            curr += 1
        
        off = offset - start*blksz
        return mv_ret[off : off+length]
    
    def read_block(self, blkid):
        return self.dmup.spa.reader.read(self.get_blkptr(blkid))
    
    def get_blkptr(self, blkid):
        BLKPTR_SHFT = 7
        if self.phys.dn_nlevels > 1:
            assert(self.phys.dn_indblkshift > BLKPTR_SHFT)
            BLKID_MASK = (1 << (self.phys.dn_indblkshift - BLKPTR_SHFT)) - 1
        
        blkid_arr = []
        for i in range(self.phys.dn_nlevels):
            blkid_arr.append(blkid)
            # blkid = blkid * blkptr_sz / ind_blk_sz
            blkid >>= (self.phys.dn_indblkshift - BLKPTR_SHFT)
        assert(blkid_arr[-1] < self.phys.dn_nblkptr)
        
        blkptr = self.phys.dn_blkptr[blkid_arr.pop()]
        while len(blkid_arr) > 0:
            data = memoryview(self.dmup.spa.reader.read(blkptr))
            blkid = blkid_arr.pop() & BLKID_MASK
            blkptr = BlkPtr(data[blkid<<BLKPTR_SHFT : (blkid+1)<<BLKPTR_SHFT])
        
        return blkptr

class Zap(DNode):
    def __init__(self, dmup, phys):
        super(type(self),self).__init__(dmup, phys)
        self.zap_phys = ZapPhys(self.read_block(0))
        self.load_table()
    
    def load_table(self):
        zap_phys = self.zap_phys
        if zap_phys.table_embeded:
            self.table = zap_phys.table
        else:
            raise Unsupported(type(zap_phys), value='External Pointer Table')
            self.table = None
