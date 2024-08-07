# -*- coding:utf-8 -*-

from . import utils

class DVA(object):
    def __init__(self, dva_word=[0,0]):
        self.dva_word = dva_word[:]
    
    def copyin(self, other):
        self.dva_word = other.dva_word[:]
    
    def copyout(self):
        return type(self)(self.dva_word)
    
    @property
    def vdev(self):
        return utils.bitfield_read(self.dva_word[0], 32, 64)
    
    @property
    def grid(self):
        return utils.bitfield_read(self.dva_word[0], 24, 32)
    
    @property
    def asize(self):
        return utils.bitfield_read(self.dva_word[0], 0, 24)
    
    @property
    def gang(self):
        gang = utils.bitfield_read(self.dva_word[1], 63, 64)
        if gang:
            raise Exception('GANG not supported')
        return gang
    
    @property
    def offset(self):
        return utils.bitfield_read(self.dva_word[1], 0, 63)
    
    def __str__(self):
        raw = ':'.join([hex(i)[2:] for i in self.dva_word])
        return 'v%X.o%x.s%x.g%x.g%x<%s>' % (
            self.vdev, self.offset, self.asize, self.gang, self.grid, raw)
    __repr__ = __str__

class ZioCkSum(object):
    def __init__(self, zc_word=[0,0,0,0]):
        self.zc_word = zc_word[:]
    
    def copyin(self, other):
        self.zc_word = other.zc_word[:]
    
    def copyout(self):
        return type(self)(self.zc_word)
    
    def __str__(self):
        tohex = lambda n : hex(n)[2:].zfill(16)
        return '[%s]' % ', '.join([tohex(i) for i in self.zc_word])
    __repr__ = __str__

class BlkPtrProp(object):
    def __init__(self, blk_prop):
        self.blk_prop = blk_prop
    
    def __str__(self):
        s  = hex(self.blk_prop)[2:]
        s += '{' + 'E:' + str(self.endian)
        s += '|' + 'dedup:' + str(self.dedup)
        s += '|' + 'crypt:' + str(self.crypt)
        s += '|' + 'lvl:' + str(self.level)
        s += '|' + 'type:' + str(self.type)
        
        if self.embeded:
            s += '|' + 'e_type:' + str(self.e_type)
        else:
            s += '|' + 'cksum:' + str(self.cksum)
        
        s += '|' + 'embed:' + str(self.embeded)
        s += '|' + 'comp:' + str(self.compress)
        
        if self.embeded:
            s += '|' + 'e_psize:' + str(self.e_psize)
            s += '|' + 'e_lsize:' + str(self.e_lsize)
        else:
            s += '|' + 'psize:' + str(self.psize)
            s += '|' + 'lsize:' + str(self.lsize)
        
        s += '}'
        return s
    
    __repr__ = __str__
    
    @property
    def endian(self):
        return utils.bitfield_read(self.blk_prop, 63, 64)
    
    @property
    def dedup(self):
        return utils.bitfield_read(self.blk_prop, 62, 63)
    
    @property
    def crypt(self):
        return utils.bitfield_read(self.blk_prop, 61, 62)
    
    @property
    def level(self):
        return utils.bitfield_read(self.blk_prop, 56, 61)
    
    @property
    def type(self):
        return utils.bitfield_read(self.blk_prop, 48, 56)
    
    @property
    def cksum(self):
        assert(not self.embeded)
        return utils.bitfield_read(self.blk_prop, 40, 48)
    
    @property
    def e_type(self):
        assert(self.embeded)
        return utils.bitfield_read(self.blk_prop, 40, 48)
    
    @property
    def embeded(self):
        return utils.bitfield_read(self.blk_prop, 39, 40)
    
    @property
    def compress(self):
        return utils.bitfield_read(self.blk_prop, 32, 39)
    
    @property
    def e_psize(self):
        assert(self.embeded)
        return utils.bitfield_read(self.blk_prop, 25, 32)
    
    @property
    def e_lsize(self):
        assert(self.embeded)
        return utils.bitfield_read(self.blk_prop, 0, 25)
    
    @property
    def psize(self):
        assert(not self.embeded)
        return utils.bitfield_read(self.blk_prop, 16, 32)
    
    @property
    def lsize(self):
        assert(not self.embeded)
        return utils.bitfield_read(self.blk_prop, 0, 16)

class BlkPtr(utils.CStruct):
    FIELDS,SIZE_U64 = [],0
    
    @classmethod
    def initFields(cls):
        if not cls.FIELDS:
            conv_dva     = lambda d : [DVA(d[0:2]),DVA(d[2:4]),DVA(d[4:6])]
            conv_prop    = lambda d : BlkPtrProp(int(d[0]))
            conv_int     = lambda d : int(d[0])
            conv_int_arr = lambda d : d[:]
            conv_cksum   = lambda d : ZioCkSum(d[:])
            fmt_hex_arr  = lambda arr : ','.join([hex(i) for i in arr])
            
            make = lambda name,szInU64,convert,formatter : (cls.FIELDS.append(
                utils.CStructField(name,szInU64,convert,formatter)
            ))
            
            make('blk_dva',        6, conv_dva,     str         )
            make('blk_prop',       1, conv_prop,    str         )
            make('blk_pad',        2, conv_int_arr, fmt_hex_arr )
            make('blk_phys_birth', 1, conv_int,     str         )
            make('blk_birth',      1, conv_int,     str         )
            make('blk_fill',       1, conv_int,     str         )
            make('blk_cksum',      4, conv_cksum,   str         )
            
            cls.SIZE_U64 = sum([field.szInU64 for field in cls.FIELDS])
    
    def __init__(self, bins=None, ints=None, endian='little'):
        super(type(self),self).__init__(bins=bins, ints=ints, endian=endian)
        self.initFields()
        
        if ints is None:
            if bins is None:
                _endian = utils.int_to_endian(BlkPtrProp(0).endian)
                data = [0] * self.SIZE_U64
            else:
                sz = len(bins) // 8
                assert(sz >= self.SIZE_U64)
                
                _endian = self.get_endian_from_bins(bins)
                data = utils.read_u64(bins,
                    endian=_endian,
                    count=self.SIZE_U64)
        else:
            data = ints # integer array
            _endian = endian
            assert(len(data) >= self.SIZE_U64)
        
        self.setattrs_u64(data)
        assert(self.endian == _endian)
    
    @property
    def endian(self):
        return utils.int_to_endian(self.blk_prop.endian)
    
    @property
    def embeded(self):
        return self.blk_prop.embeded
    
    @property
    def dva_array(self):
        assert(not self.embeded)
        return [d for d in self.blk_dva if d.asize > 0]
    
    @classmethod
    def get_endian_from_bins(cls, bins):
        assert(len(bins) >= cls.SIZE_U64)
        # The highest bit of 'blk_prop' is endian
        off = cls.count_offset('blk_prop') + 7
        return utils.int_to_endian([utils.int_from_bytes(bins[off:off+1]) >> 7])
