# -*- coding:utf-8 -*-

import time
from .zctypes import *
from .utils import *
from .compressor import Compressor

class BlkPtrReader(object):
    def __init__(self, root_vdev):
        self.rvd = root_vdev
        assert(self.rvd.opened)
    
    def read(self, blkptr, verify=False):
        # TODO: verify whether all copies are same
        
        if blkptr.is_hole:
            raise HoleError(blkptr)
        
        compressor = Compressor.from_int(blkptr.compr)
        # TODO: what if read content not compressed?
        assert(compressor.supported)
        
        loc = blkptr.diskLocation()
        if not blkptr.embed:
            assert(len(loc['dva']) > 0)
            dva = loc['dva'][0]
            raw = self.rvd.read(
                dva['vdev'],
                dva['offset'],
                #buffer=memoryview(bytearray(dva['asize'])),
                buffer=memoryview(bytearray(loc['psize'])),
                diskOff=4*1024*1024
            )
        else:
            raw = self.read_embed(blkptr, loc)
        
        return compressor.decompress(raw, loc['lsize'])
    
    def read_embed(self, blkptr, loc):
        assert(blkptr.endian == Endian.little == Endian.default)
        return memoryview(blkptr.bytes[0:loc['psize']])

class DNode(object):
    def __init__(self, os, id, phys):
        self.os = os
        self.id = id
        self.dnphys = phys
    
    def read_block(self, blkid):
        return self.os.spa.reader.read(self.get_blkptr(blkid))
    
    def read(self, offset, length):
        blksz = self.dnphys.blksz
        start = curr = offset // blksz
        end   = (offset + length - 1) // blksz
        
        mv_ret = memoryview(bytearray(blksz * (end - start + 1)))
        while curr <= end:
            blk = memoryview(self.read_block(curr))
            mv_ret[(curr-start)*blksz:(curr-start+1)*blksz] = blk
            curr += 1
        
        off = offset - start*blksz
        ret = mv_ret[off : off+length]
        
        assert(len(ret) == length)
        return ret
    
    def get_blkptr(self, blkid):
        BLKPTR_SHFT = 7
        if self.dnphys.dn_nlevels > 1:
            assert(self.dnphys.dn_indblkshift > BLKPTR_SHFT)
            BLKID_MASK = (1 << (self.dnphys.dn_indblkshift - BLKPTR_SHFT)) - 1
        
        blkid_arr = []
        for i in range(self.dnphys.dn_nlevels):
            blkid_arr.append(blkid)
            # blkid = blkid * blkptr_sz / ind_blk_sz
            blkid >>= (self.dnphys.dn_indblkshift - BLKPTR_SHFT)
        assert(blkid_arr[-1] < self.dnphys.dn_nblkptr)
        
        blkptr = self.dnphys.dn_blkptr[blkid_arr.pop()]
        while len(blkid_arr) > 0:
            data = memoryview(self.os.spa.reader.read(blkptr))
            blkid = blkid_arr.pop() & BLKID_MASK
            blkptr = BlkPtr(data[blkid<<BLKPTR_SHFT : (blkid+1)<<BLKPTR_SHFT])
        
        return blkptr

class ObjSet(object):
    def __init__(self, spa, blkptr, ds=None):
        self.spa = spa
        self.ds = ds
        self.phys = ObjSetPhys(spa.reader.read(blkptr))
        self.metadn = DNode(os=self, id=None, phys=self.phys.os_meta_dnode)
        self.blkptr = blkptr
    
    def get(self, id, type=None, get_dnphys=False):
        orig_id = id
        if type is not None and issubclass(type,ZNode):
            id = Int(orig_id).bit_field(0,48)
        
        dnsz = DNodePhys.sizeof()
        assert(id > 0 and dnsz == 512)
        dnphys = DNodePhys(self.metadn.read(id * dnsz, dnsz))
        
        if get_dnphys:
            return dnphys
        else:
            if type is None:
                type = DNode
            return type(os=self, id=orig_id, phys=dnphys)

class DslDir(DNode):
    def __init__(self, os, id, phys):
        super(type(self),self).__init__(os=os, id=id, phys=phys)
        assert(len(phys.dn_bonus) == DslDirPhys.sizeof())
        self.phys = DslDirPhys(self.dnphys.dn_bonus)
        # Is it right that all objects of dsl-dir is stored in meta-os ?
        if self.phys.dd_child_dir_zapobj > 0:
            self.child = self.os.spa.mos.get(
                self.phys.dd_child_dir_zapobj, type=Zap)
        else:
            self.child = None
        
        self.parent_dd = None
        self.name = ''
    
    def set(self, parent=None, name=''):
        if parent:
            self.parent_dd = parent
        if name:
            self.name = name
    
    def get_ds(self, id):
        dnphys = self.os.get(id, get_dnphys=True)
        return DslDataSet(os=self.os, id=id, phys=dnphys, dsldir=self)
    
    def get_dd(self, name):
        id = self.child.lookup(name, fmt='num')[0]
        dd = self.os.get(id, type=type(self))
        dd.set(parent=self, name=name)
        return dd

class DslDataSet(DNode):
    def __init__(self, os, id, phys, dsldir=None):
        assert(dsldir is not None)
        super(type(self),self).__init__(os=os, id=id, phys=phys)
        assert(len(phys.dn_bonus) == DslDataSetPhys.sizeof())
        self.phys = DslDataSetPhys(phys.dn_bonus)
        self.dsldir = dsldir
        
        self._myos = None
        self.os_type = str(OST.from_int(self.myos.phys.os_type))
        
        if self.os_type == 'zfs':
            self._master = None
            self._rootdir = None
            self._init_attrs()
        
        elif self.os_type == 'zvol':
            self._property = None
    
    def _init_attrs(self):
        assert(self.os_type == 'zfs')
        self.obj_sa_attrs = self.master.lookup('SA_ATTRS', fmt='num')[0]
        self.zap_sa_attrs = self.myos.get(self.obj_sa_attrs, type=Zap)
        
        self.obj_registry = self.zap_sa_attrs.lookup('REGISTRY', fmt='num')[0]
        self.zap_registry = self.myos.get(self.obj_registry, type=Zap)
        
        self.obj_layouts = self.zap_sa_attrs.lookup('LAYOUTS', fmt='num')[0]
        self.zap_layouts = self.myos.get(self.obj_layouts, type=Zap)
        
        assert(self.zap_registry.is_micro)
        
        entries = []
        self.zap_registry.ls(entries=entries)
        entries.sort(key = lambda chk : Int(chk.mze_value).bit_field(0,16))
        
        self.registry_dict,self.registry_list = {},[]
        for chk in entries:
            val = Int(chk.mze_value)
            ent = {
                'name'  : chk.mze_name,
                'num'   : val.bit_field( 0,16),
                'len'   : val.bit_field(24,16),
                'bswap' : val.bit_field(16, 8),
            }
            self.registry_dict[ent['num']] = ent
            self.registry_list.append(ent)
        
        self.registry_list.sort(key = lambda ent : ent['num'])
    
    def ls_layouts(self, layout_num=None):
        assert(self.os_type == 'zfs')
        if layout_num is None:
            self.zap_layouts.ls()
        else:
            entries = []
            for num in self.zap_layouts.lookup(str(layout_num), fmt='num'):
                entries.append(self.registry_dict[num])
            self.ls_registry(entries)
    ls_layout = ls_layouts
    
    def get_layout(self, layout_num):
        assert(self.os_type == 'zfs')
        entries = []
        for num in self.zap_layouts.lookup(str(layout_num), fmt='num'):
            ent = self.registry_dict[num]
            entries.append({k:ent[k] for k in ent})
        return entries
    
    def ls_registry(self, entries=None):
        assert(self.os_type == 'zfs')
        if entries is None:
            entries = self.registry_list
        
        keylen = max([len(ent['name']) for ent in entries])
        print('\n'.join([
            '%-*s : num=%02d, len=%02d, bswap=%d' % (
                keylen, ent['name'], ent['num'], ent['len'], ent['bswap']
            ) for ent in entries
        ]))
    
    @property
    def myos(self):
        if not self._myos:
            self._myos = ObjSet(
                spa    = self.os.spa,
                blkptr = self.phys.ds_bp,
                ds     = self
            )
        return self._myos
    
    @property
    def master(self):
        assert(self.os_type == 'zfs')
        if self._master is None:
            self._master = self.myos.get(1, type=Zap)
        return self._master
    
    @property
    def rootdir(self):
        assert(self.os_type == 'zfs')
        if self._rootdir is None:
            obj = self.master.lookup('ROOT',fmt='num')[0] | (int(DT.dir) << 60)
            self._rootdir = self.myos.get(obj, type=ZNode)
        return self._rootdir
    
    @property
    def property(self):
        assert(self.os_type == 'zvol')
        if self._property is None:
            self._property = self.myos.get(2, type=Zap)
        return self._property

class SA(object):
    def __init__(self, znode, bonus_type):
        if bonus_type == 'bonus':
            buffer = znode.dnphys.dn_bonus
        else:
            assert(bonus_type == 'spill')
            buffer = znode.os.spa.reader.read(znode.dnphys.dn_spill)
        
        self.znode = znode
        self.bonus_type = bonus_type
        self.phys = SaHdrPhys(buffer)
        self.attrs = []
        self.inited = False
    
    def do_init(self):
        if self.inited:
            return
        
        conv_unsigned = lambda b,e : Int.from_bytes(b,endian=e)
        
        self.convert_table = {
            'ZPL_ATIME'      : self.convert_time_buffer,
            'ZPL_MTIME'      : self.convert_time_buffer,
            'ZPL_CTIME'      : self.convert_time_buffer,
            'ZPL_CRTIME'     : self.convert_time_buffer,
            'ZPL_GEN'        : conv_unsigned,
            'ZPL_MODE'       : conv_unsigned,
            'ZPL_SIZE'       : conv_unsigned,
            'ZPL_PARENT'     : conv_unsigned,
            'ZPL_LINKS'      : conv_unsigned,
            'ZPL_XATTR'      : conv_unsigned, # TODO: the usage of xattr?
            'ZPL_RDEV'       : conv_unsigned,
            'ZPL_FLAGS'      : conv_unsigned,
            'ZPL_UID'        : conv_unsigned,
            'ZPL_GID'        : conv_unsigned,
            'ZPL_DACL_COUNT' : conv_unsigned,
            'ZPL_PROJID'     : conv_unsigned,
            'ZPL_DACL_ACES'  : ZfsAceHdr.from_bytes, # TODO: parse ACE mask ...
        }
        
        layout = self.znode.os.ds.get_layout(self.phys.layout_num)
        
        zeros = [i for i in range(len(layout)) if layout[i]['len'] == 0]
        if len(zeros) > 0:
            lengths = self.phys.sa_lengths
            assert(len(lengths) == len(zeros))
            for i in range(len(zeros)):
                assert(lengths[i] > 0)
                layout[zeros[i]]['len'] = lengths[i]
        
        self.layout = layout
        self.parse_attrs()
        self.inited = True
    
    def parse_attrs(self):
        pos,self.attrs = 0,[]
        for ent in self.layout:
            if ent['name'] in self.convert_table:
                conv = self.convert_table[ent['name']]
            else:
                conv = lambda _1,_2 : None
            
            buffer = self.phys.attr_buffer[pos:pos+ent['len']]
            self.attrs.append({
                'NAME'   : ent['name'],
                'name'   : ent['name'][4:].lower(),
                'buffer' : buffer,
                'bswap'  : ent['bswap'],
                'value'  : conv(buffer, self.phys.endian)
            })
            pos += ent['len']
    
    def ls(self):
        self.do_init()
        keylen = max([len(a['name']) for a in self.attrs ])
        for i in range(len(self.attrs)):
            attr = self.attrs[i]
            if attr['NAME'] == 'ZPL_DACL_ACES':
                print('[%02d]%-*s : <%d>' % (
                    i, keylen,attr['name'],len(attr['value'])))
            else:
                print('[%02d]%-*s : %s' % (
                    i, keylen,attr['name'],str(attr['value'])))
    
    @classmethod
    def convert_time_buffer(cls, buffer, endian, fmt='%Y/%m/%d %H:%M:%S'):
        sec,nsec = Int.from_bytes_to_list(buffer, int_size=8, endian=endian)
        if nsec >= 1000 * 1000:
            assert(nsec < 1e9)
            str_nsec = ('%.9f' % (nsec * 1e-9))[2:][:3]
        return '%s.%s[%s]' % (
            time.strftime(fmt,time.localtime(sec)), str_nsec, time.tzname[-1]
        )

class ZNode(DNode):
    def __init__(self, os, id, phys):
        rawId = Int(id)
        dt,id = DT.from_int(rawId.bit_field(60,4)), rawId.bit_field(0,48)
        
        assert(os.ds)
        super(type(self),self).__init__(os=os, id=id, phys=phys)
        self.dt = dt
        
        self.sa_bonus = SA(self, 'bonus')
        if self.dnphys.dn_spill:
            self.sa_spill = SA(self, 'spill')
        else:
            self.sa_spill = None
        
        if self.dt == DT.dir:
            self.zap = Zap(os, id, self.dnphys)
            self.items = {}
    
    @property
    def is_dir(self):
        return self.dt == DT.dir
    
    def ls_dir(self):
        assert(self.is_dir)
        self.zap.ls(fmt=hex)
    
    def get(self, name):
        assert(self.is_dir)
        if name not in self.items:            
            objid = self.zap.lookup(name, fmt='num')[0]
            self.items[name] = self.os.get(objid, type=type(self))
        return self.items[name]

class SpaceMap(DNode):
    def __init__(self, os, id, phys):
        super(type(self),self).__init__(os=os, id=id, phys=phys)
        self.phys = SpaceMapPhys(self.dnphys.dn_bonus)

class Zap(DNode):
    def __init__(self, os, id, phys):
        super(type(self),self).__init__(os=os, id=id, phys=phys)
        self.crc = Crc64Poly
        self.phys = ZapPhys.from_bytes(self.read_block(0))
        self.is_micro = self.phys.is_micro
        self.load_table()
    
    def ls(self, keys=None, entries=None, fmt=str):
        if keys is None:
            names = []
        else:
            names = keys
        
        if self.is_micro:
            self.ls_mzap(keys=names, entries=entries)
        else:
            self.ls_fat(keys=names, entries=entries)
        
        if keys is None and entries is None:
            if not names:
                print('No entries in the zap object')
                return
            
            keylen = max([len(key) for key in names])
            for key in names:
                if self.is_micro:
                    print('%-*s : %s' % (keylen, key,
                        fmt(self.phys.items[key].mze_value)))
                else:
                    ent = self.lookup(key)
                    if ent['intlen'] > 1:
                        value = Int.from_bytes_to_list(ent['value'],
                            int_size=ent['intlen'],
                            endian=Endian.big)
                        if len(value) == 1:
                            value = value[0]
                    else:
                        value = '--'
                    print('%-*s : %s' % (keylen, key, fmt(value)))
    
    def ls_mzap(self, keys=None, entries=None):
        for chunk in self.phys.mz_chunk:
            if entries is not None:
                entries.append(chunk)
            keys.append(chunk.mze_name)
    
    def ls_fat(self, keys=None, entries=None):
        cursor = self.cursor_init()
        while self.cursor_retrieve(cursor):
            if entries is not None:
                entries.append(cursor['entry'])
            keys.append(cursor['entry']['name'])
            self.cursor_advance(cursor)
    
    def lookup(self, key, fmt=None):
        '''The argument fmt should be one of ['str','num',None]'''
        if self.is_micro:
            if fmt is not None:
                assert(fmt == 'num')
                return [self.phys.items[key].mze_value]
            else:
                return self.phys.items[key]
        
        hash = self.hash(key)
        leaf = self.leaf(self.hash2blk(hash))
        
        id = leaf.l_hash[self.leaf_hash(leaf,hash)]
        while id != leaf.CHAIN_END:
            le = leaf.l_chunk[id].l_entry
            if le.le_hash == hash and key == self.deref_entry_key(leaf,le):
                return self.deref_entry(leaf,le,fmt)
            id = le.le_next
        
        raise Exception('key{%s} not found' % key)
    
    def hashbits(self):
        if self.is_micro:
            flags = 0
        else:
            flags = self.phys.zap_flags
        
        return {
            True  : 48,
            False : 28,
        }[ZapF.hash64.has(flags)]
    
    def hash(self, key):
        assert(self.phys.zap_normflags == 0)
        mask = ~((1 << (64 - self.hashbits())) - 1)
        return self.crc.hash(key, self.phys.zap_salt) & mask
    
    def cursor_init(self):
        return {
            'hash'       : 0,
            'cd'         : 0,
            'leaf_blkid' : -1,
        }
    
    def leaf_hash(self, leaf, hash):
        blk_shift = Int(self.dnphys.blksz).highbit() - 1
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
                blk_shift = Int(self.dnphys.blksz).highbit() - 1
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
    
    def deref_entry_key(self, leaf, entry):
        return Str.decode(leaf.read(
            entry.le_name_chunk, entry.le_name_numints
        ))
    
    def deref_entry(self,leaf,entry,fmt=None,name=None):
        if name is None:
            name = self.deref_entry_key(leaf,entry)
        
        # Notes: value is encoded in big-endian
        val_len = entry.le_value_intlen * entry.le_value_numints
        value = leaf.read(entry.le_value_chunk, val_len)
        if fmt == 'str':
            value = Str.decode(value)
        elif fmt == 'num':
            value = Int.from_bytes_to_list(value,
                int_size=entry.le_value_intlen, endian=Endian.big)
        
        ret = {
            'name'    : self.deref_entry_key(leaf,entry),
            'value'   : value,
            'intlen'  : entry.le_value_intlen,
            'numints' : entry.le_value_numints,
            'hash'    : entry.le_hash,
            'cd'      : entry.le_cd,
        }
        if fmt is None:
            return ret
        else:
            return ret['value']
    
    def load_table(self):
        if self.is_micro:
            return
        
        if self.phys.table_embeded:
            self.table = self.phys.table
        else:
            raise Unsupported(self,
                value='External Pointer Table')
            self.table = None
    
    def leaf(self, blkid):
        return ZapLeafPhys(self.read_block(blkid))
    
    def hash2blk(self, hash):
        return self.table[hash >> (64 - self.phys.zap_ptrtbl.zt_shift)]
