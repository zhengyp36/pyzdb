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
        self.crc = Crc64Poly()
        self.is_micro = False
        self.zap_phys = ZapPhys(self.read_block(0))
        self.load_table()
    
    def ls(self, keys=None, entries=None):
        if keys is None:
            names = []
        else:
            names = keys
        
        cursor = self.cursor_init()
        while self.cursor_retrieve(cursor):
            if entries is not None:
                entries.append(cursor['entry'])
            names.append(cursor['entry']['name'])
            self.cursor_advance(cursor)
        
        if keys is None and entries is None:
            print('\n'.join(names))
    
    def lookup(self, key, fmt=None):
        '''The argument fmt should be one of ['str','num',None]'''
        hash = self.hash(key)
        leaf = self.leaf(self.hash2blk(hash))
        
        id = leaf.l_hash[self.leaf_hash(leaf,hash)]
        while id != leaf.CHAIN_END:
            le = leaf.l_chunk[id].l_entry
            if le.le_hash == hash and key == self.deref_entry_key(leaf,le):
                return self.deref_entry(leaf,le,fmt)
            id = le.le_next
        
        return None
    
    def hashbits(self):
        if self.is_micro:
            flags = 0
        else:
            flags = self.zap_phys.zap_flags
        
        return {
            True  : 48,
            False : 28,
        }[ZapF.hash64.has(flags)]
    
    def hash(self, key):
        assert(self.zap_phys.zap_normflags == 0)
        mask = ~((1 << (64 - self.hashbits())) - 1)
        return self.crc.hash(key, self.zap_phys.zap_salt) & mask
    
    def cursor_init(self):
        return {
            'hash'       : 0,
            'cd'         : 0,
            'leaf_blkid' : -1,
        }
    
    def leaf_hash(self, leaf, hash):
        blk_shift = Int(self.phys.blksz).highbit() - 1
        leaf_hash_shift = blk_shift - 5
        shift = leaf_hash_shift + leaf.l_hdr.lh_prefix_len
        mask = (1 << leaf_hash_shift) - 1
        return (hash >> (64 - shift)) & mask
    
    def cursor_retrieve(self, cursor):
        gteq = lambda h1,cd1,h2,cd2 : (h1 > h2) or (h1 == h2 and cd1 >= cd2)
        satisfy = lambda le,besth,bestcd : (
            gteq(le.le_hash, le.le_cd, cursor['hash'], cursor['cd']) and
            gteq(besth, bestcd, le.le_hash, le.le_cd))
        
        def deref_leaf():
            blk = self.hash2blk(cursor['hash'])
            if cursor['leaf_blkid'] != blk:
                cursor['leaf_blkid'] = blk
                cursor['leaf'] = self.leaf(blk)
                blk_shift = Int(self.phys.blksz).highbit() - 1
                leaf_hash_shift = blk_shift - 5
                cursor['nentry'] = 1 << leaf_hash_shift
            return cursor['leaf']
        
        def get_closest(leaf):
            besth,bestcd,bestle = (1<<64)-1,(1<<32)-1,None
            lh,bestlh = self.leaf_hash(leaf,cursor['hash']),cursor['nentry']-1
            while lh <= bestlh:
                id = leaf.l_hash[lh]
                while id != leaf.CHAIN_END:
                    le = leaf.l_chunk[id].l_entry
                    if satisfy(le,besth,bestcd):
                        bestlh = lh
                        besth  = le.le_hash
                        bestcd = le.le_cd
                        bestle = le
                    id = le.le_next
                lh += 1
            return bestle
        
        while True:
            if cursor['hash'] == -1:
                return False
            else:
                leaf = deref_leaf()
                le = get_closest(leaf)
                if le is not None:
                    break
                
                if leaf.l_hdr.lh_prefix_len == 0:
                    cursor['hash'] = -1
                    cursor['cd'] = 0
                    return False
                
                nocare = (1 << (64 - leaf.l_hdr.lh_prefix_len)) - 1
                cursor['hash'] = (cursor['hash'] & ~nocare) + nocare + 1
                cursor['cd'] = 0
                cursor['leaf_blkid'] = -1
        
        cursor['hash'] = le.le_hash
        cursor['cd'] = le.le_cd
        cursor['entry'] = self.deref_entry(leaf,le)
        return True
    
    def cursor_advance(self, cursor):
        cursor['cd'] += 1
    
    def decode_str(self, bytes):
        return {
            '2' : lambda bin : str(bytearray(bin)),
            '3' : lambda bin : bytearray(bin).decode('utf-8'),
        }[sys.version[0]](bytes).strip('\x00')
    
    def deref_entry_key(self, leaf, entry):
        return self.decode_str(leaf.read(
            entry.le_name_chunk, entry.le_name_numints
        ))
    
    def deref_entry(self,leaf,entry,fmt=None,name=None):
        if name is None:
            name = self.deref_entry_key(leaf,entry)
        
        # Notes: value is encoded in big-endian
        val_len = entry.le_value_intlen * entry.le_value_numints
        value = leaf.read(entry.le_value_chunk, val_len)
        if fmt == 'str':
            value = self.decode_str(value)
        elif fmt == 'num':
            value = Int.from_bytes_to_list(value,
                int_size=entry.le_value_intlen, endian=Endian.big)
        
        return {
            'name'    : self.deref_entry_key(leaf,entry),
            'value'   : value,
            'intlen'  : entry.le_value_intlen,
            'numints' : entry.le_value_numints,
            'hash'    : entry.le_hash,
            'cd'      : entry.le_cd,
        }
    
    def load_table(self):
        if self.zap_phys.table_embeded:
            self.table = self.zap_phys.table
        else:
            raise Unsupported(type(self.zap_phys),
                value='External Pointer Table')
            self.table = None
    
    def leaf(self, blkid):
        return ZapLeafPhys(self.read_block(blkid))
    
    def hash2blk(self, hash):
        return self.table[hash >> (64 - self.zap_phys.zap_ptrtbl.zt_shift)]
