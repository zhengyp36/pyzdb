# -*- coding:utf-8 -*-

from .utils import *

class DVA(CStruct):
    STRUCT_NAME = 'dva_t'
    FIELDS = [['dva_word', 16, 'u64.array', 'str']]
    
    def _validate(self):
        bitfields = {
            'asize'  : [ 0,  0, 24 ],
            'grid'   : [ 0, 24,  8 ],
            'vdev'   : [ 0, 32, 32 ],
            'offset' : [ 1,  0, 63 ],
            'gang'   : [ 1, 63,  1 ],
        }
        
        words = [Int(w) for w in self.dva_word]
        for name in bitfields:
            idx,start,length = bitfields[name]
            val = words[idx].bit_field(start,length)
            setattr(self, name, val)
    
    def __str__(self):
        raw = ':'.join([hex(w)[2:] for w in self.dva_word])
        return 'v%X.o%x.s%x.G%x.g%x<%s>' % (
            self.vdev, self.offset, self.asize, self.gang, self.grid, raw)

class ZioCkSum(CStruct):
    STRUCT_NAME = 'zio_cksum_t'
    FIELDS = [['zc_word', 32, 'u64.array', 'str']]
    
    def __str__(self):
        fmt = lambda n : hex(n)[2:].zfill(16)
        return '[%s]' % ', '.join([fmt(i) for i in self.zc_word])

class BlkPtr(CStruct):
    # TODO: Is the method of reading by Endian right?
    #       Is the bit position of E in blkptr_t.blk_prop right?
    
    STRUCT_NAME = 'blkptr_t'
    FIELDS = [
        [ 'blk_dva',       48, DVA,         'str' ],
        [ 'blk_prop',       8, 'u64',       None  ], # __blk_prop_formatter
        [ 'blk_pad',       16, 'u64.array', 'str' ],
        [ 'blk_phys_birth', 8, 'u64',       'str' ],
        [ 'blk_birth',      8, 'u64',       'str' ],
        [ 'blk_fill',       8, 'u64',       'str' ],
        [ 'blk_cksum',     32, ZioCkSum,    'str' ],
    ]
    
    FIELDS_PROP_NORMAL = [
        [ 'lsize',  0, 16 ],
        [ 'psize', 16, 16 ],
        [ 'compr', 32,  7 ],
        [ 'embed', 39,  1 ],
        [ 'cksum', 40,  8 ],
        [ 'type',  48,  8 ],
        [ 'level', 56,  5 ],
        [ 'crypt', 61,  1 ],
        [ 'dedup', 62,  1 ],
        [ 'E',     63,  1 ],
    ]
    
    FIELDS_PROP_EMBED = [
        [ 'lsize',  0, 25 ],
        [ 'psize', 25,  7 ],
        [ 'compr', 32,  7 ],
        [ 'embed', 39,  1 ],
        [ 'etype', 40,  8 ],
        [ 'type',  48,  8 ],
        [ 'level', 56,  5 ],
        [ 'crypt', 61,  1 ],
        [ 'dedup', 62,  1 ],
        [ 'E',     63,  1 ],
    ]
    
    def _set_endian(self, bytes, endian):
        offset = self.count_offset('blk_prop') + 7
        prop = Int.from_bytes(bytes[offset:offset+1])
        
        E = Int(prop).bit_field(7,1)
        self._endian = Endian.from_int(E)
    
    def _validate(self):
        E = Int(self.blk_prop).bit_field(63,1)
        assert(self.endian == Endian.from_int(E))
        
        if Int(self.blk_prop).bit_field(39,1):
            bitfields = self.FIELDS_PROP_EMBED
        else:
            bitfields = self.FIELDS_PROP_NORMAL
        
        prop = Int(self.blk_prop)
        for bf in bitfields:
            setattr(self, bf[0], prop.bit_field(*bf[1:3]))
        
        assert(self.endian == Endian.from_int(self.E))
    
    FIELDS_INITED = False
    @classmethod
    def _init_this_type(cls):
        if not cls.FIELDS_INITED:
            formatters = {
                'blk_prop' : cls.__blk_prop_formatter
            }
            
            for f in cls.FIELDS:
                if f[0] in formatters:
                    f[3] = formatters[f[0]]
            
            cls.FIELDS_INITED = True
    
    @staticmethod
    def __blk_prop_formatter(value, inst):
        if inst.embed:
            bitfields = inst.FIELDS_PROP_EMBED
        else:
            bitfields = inst.FIELDS_PROP_NORMAL
        
        output = []
        for bf in bitfields:
            output.append('%s.%s' % (
                bf[0], str(getattr(inst,bf[0]))
            ))
        
        return '{%s}<%s>' % ('|'.join(output), hex(value).strip('L'))
    
    def __str__(self):
        if self.embed:
            fields = ['blk_prop','blk_birth']
            checker = lambda f : f[0] in fields
            keylen = max([len(f) for f in fields])
        else:
            checker,keylen = None,None
        
        return self.do_format(checker=checker, keylen=keylen)
    
    __repr__ = __str__

class UberBlock(CStruct):
    STRUCT_NAME = 'uberblock_t'
    FIELDS = [
        [ 'ub_magic',            8, 'u64',  'str'     ],
        [ 'ub_version',          8, 'u64',  'str'     ],
        [ 'ub_txg',              8, 'u64',  'str'     ],
        [ 'ub_guid_sum',         8, 'u64',  'magic32' ],
        [ 'ub_timestamp',        8, 'u64',  'str'     ],
        [ 'ub_rootbp',         128, BlkPtr, '--'      ],
        [ 'ub_software_version', 8, 'u64',  'str'     ],
        [ 'ub_mmp_magic',        8, 'u64',  'magic32' ],
        [ 'ub_mmp_delay',        8, 'u64',  'str'     ],
        [ 'ub_mmp_config',       8, 'u64',  'str'     ],
        [ 'ub_checkpoint_txg',   8, 'u64',  'str'     ],
    ]
    UBERBLOCK_MAGIC = 0x00bab10c # oo-ba-block
    
    def _set_endian(self, bytes, endian):
        magic_buf = bytes[0:8]
        magic = Int.from_bytes(magic_buf, endian=Endian.little)
        if magic == self.UBERBLOCK_MAGIC:
            self._endian = Endian.little
        else:
            magic = Int.from_bytes(magic_buf, endian=Endian.big)
            if magic != self.UBERBLOCK_MAGIC:
                raise MagicError(type(self))
            self._endian = Endian.big
    
    def _validate(self):
        assert(self.ub_magic == self.UBERBLOCK_MAGIC)
        assert(self.endian == self.ub_rootbp.endian)
