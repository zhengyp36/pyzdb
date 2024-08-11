# -*- coding:utf-8 -*-
# zctypes is zfs-C-Types

from .utils import *

class DVA(CStruct):
    STRUCT_NAME = 'dva_t'
    FIELDS = [['dva_word', 16, 'u64.array', 'str']]
    
    def _do_init(self, bytes):
        self.set_fields(bytes)
        
        bitfields = {
            'asize'  : [ 0,  0, 24 ],
            'grid'   : [ 0, 24,  8 ],
            'vdev'   : [ 0, 32, 32 ], # TODO: vdev=dva_word[0][32:32+24?]
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
    
    @property
    def empty(self):
        return self.dva_word[0] == 0 and self.dva_word[1] == 0

class ZioCkSum(CStruct):
    STRUCT_NAME = 'zio_cksum_t'
    FIELDS = [['zc_word', 32, 'u64.array', 'str']]
    
    def __str__(self):
        fmt = lambda n : hex(n)[2:].zfill(16)
        return '[%s]' % ', '.join([fmt(i) for i in self.zc_word])

class BlkPtr(CStruct):
    # TODO: Is the method of reading by Endian right?
    #       Is the bit position of E in blkptr_t.blk_prop right?
    
    dva_conv = DVA.convert_method(count=3)
    dva_fmt  = lambda arr,_ : '[%s]' % ','.join([str(dva) for dva in arr])
    
    STRUCT_NAME = 'blkptr_t'
    FIELDS = [
        [ 'blk_dva',       48, dva_conv,    dva_fmt ],
        [ 'blk_prop',       8, 'u64',       None    ], # __blk_prop_formatter
        [ 'blk_pad',       16, 'u64.array', 'str'   ],
        [ 'blk_phys_birth', 8, 'u64',       'str'   ],
        [ 'blk_birth',      8, 'u64',       'str'   ],
        [ 'blk_fill',       8, 'u64',       'str'   ],
        [ 'blk_cksum',     32, ZioCkSum,    'str'   ],
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
    
    def _do_init(self, bytes):
        self._init_once()
        self._set_endian(bytes)
        self.set_fields(bytes)
        self._set_prop_fields()
    
    @classmethod
    def _init_once(cls):
        if not cls._INITED_ONCE:
            idx = cls.indexof('blk_prop', verify=True)
            cls.FIELDS[idx][3] = cls.__blk_prop_formatter
            cls._INITED_ONCE = True
    _INITED_ONCE = False
    
    def _set_endian(self, bytes):
        offset = self.offsetof('blk_prop') + 7
        prop = Int.from_bytes(bytes[offset:offset+1])
        
        E = Int(prop).bit_field(7,1)
        self._endian = Endian.from_int(E)
    
    def _set_prop_fields(self):
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
    
    def diskLocation(self, shift=9, diskOff=4*1024*1024):
        assert(not self.embed)
        
        dva_arr,idx = [],0
        for dva in self.blk_dva:
            if dva.asize:
                dva_arr.append({
                    'index'  : idx,
                    'vdev'   : dva.vdev,
                    'offset' : diskOff + (dva.offset << shift),
                    'asize'  : dva.asize << shift,
                    'gang'   : dva.gang,
                    'grid'   : dva.grid,
                })
            idx += 1
        
        return {
            'dva'   : dva_arr,
            'psize' : (self.psize + 1) << shift,
            'lsize' : (self.lsize + 1) << shift,
        }
    
    @property
    def is_hole(self):
        return not self.embed and self.blk_dva[0].empty
    
    def __str__(self):
        if self.embed:
            fields = ['blk_prop','blk_birth']
            checker = lambda f : f[0] in fields
            keylen = max([len(f) for f in fields])
        else:
            checker,keylen = None,None
        
        return self.do_format(checker=checker, keylen=keylen)
    
    # __repr__ = __str__

BLKPTR_LEN = BlkPtr.sizeof()

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
    
    def _do_init(self, bytes):
        def retrieve_endian():
            magic_buf = bytes[0:8]
            for endian in [Endian.little,Endian.big]:
                magic = Int.from_bytes(magic_buf, endian=endian)
                if magic == self.UBERBLOCK_MAGIC:
                    return endian
            raise MagicError(type(self))
        
        self._endian = retrieve_endian()
        self.set_fields(bytes)
        assert(self.ub_magic == self.UBERBLOCK_MAGIC)
        assert(self.endian == self.ub_rootbp.endian)

@EnumType
class DMUOT(object):
    '''DMUOT is dmu-object-type

convert DMUOT.TABLE from C-code by the method below:
----------------------------------------------------------------------------
def convert(fileIn, fileOut):
    def validate(line):
        line = line.strip()
        if '/*' in line:
            line = line[:line.index('/*')].strip()
        if line.startswith('DMU_OT'):
            return line
        else:
            return ''
    
    def readLine(line):
        if '=' not in line:
            name = line.strip(',').strip()
            short = name.split('DMU_OT_')[1].lower()
            value = 'None'
        else:
            arr = line.split('=')
            name = arr[0].strip()
            short = name.split('DMU_OTN_')[1].lower()
            value = arr[1].strip().strip(',').strip()
        
        quote = lambda s : "'%s'," % s
        return [quote(short),quote(name),value]
    
    def writeLine(entry, kl0, kl1, kl2, tab=8*' '):
        return '%s[ %-*s %-*s %-*s ],' % (
            tab, kl0,entry[0], kl1,entry[1], kl2,entry[2]
        )
    
    tableIn = [ readLine(validate(l)) for l in open(fileIn) if validate(l) ]
    
    kl0 = max([ len(entry[0]) for entry in tableIn ])
    kl1 = max([ len(entry[1]) for entry in tableIn ])
    kl2 = max([ len(entry[2]) for entry in tableIn ])
    tableOut = [ writeLine(e,kl0,kl1,kl2) for e in tableIn ]
    
    open(fileOut,'w').write('\\n'.join(tableOut) + '\\n')

convert('dmu_object_type_t.txt', 'dmu_object_type_t.out.txt')
----------------------------------------------------------------------------'''
    
    B_FALSE              = 0
    B_TRUE               = 1
    
    DMU_BSWAP_UINT8      = 0
    DMU_BSWAP_UINT16     = 1
    DMU_BSWAP_UINT32     = 2
    DMU_BSWAP_UINT64     = 3
    DMU_BSWAP_ZAP        = 4
    DMU_BSWAP_DNODE      = 5
    DMU_BSWAP_OBJSET     = 6
    DMU_BSWAP_ZNODE      = 7
    DMU_BSWAP_OLDACL     = 8
    DMU_BSWAP_ACL        = 9
    
    # DMU_OT_NEWTYPE       = 0x80
    # DMU_OT_METADATA      = 0x40
    # DMU_OT_ENCRYPTED     = 0x20
    # DMU_OT_BYTESWAP_MASK = 0x1f
    
    DMU_OT = lambda byteswap, metadata, encrypted : (
        0x80                            | # DMU_OT_NEWTYPE
        (int(not not metadata)  * 0x40) | # DMU_OT_METADATA
        (int(not not encrypted) * 0x20) | # DMU_OT_ENCRYPTED
        (byteswap & 0x1f)                 # DMU_OT_BYTESWAP_MASK
    )
    
    TABLE = [
        [ 'none',                 'DMU_OT_NONE',                 None                                       ],
        [ 'object_directory',     'DMU_OT_OBJECT_DIRECTORY',     None                                       ],
        [ 'object_array',         'DMU_OT_OBJECT_ARRAY',         None                                       ],
        [ 'packed_nvlist',        'DMU_OT_PACKED_NVLIST',        None                                       ],
        [ 'packed_nvlist_size',   'DMU_OT_PACKED_NVLIST_SIZE',   None                                       ],
        [ 'bpobj',                'DMU_OT_BPOBJ',                None                                       ],
        [ 'bpobj_hdr',            'DMU_OT_BPOBJ_HDR',            None                                       ],
        [ 'space_map_header',     'DMU_OT_SPACE_MAP_HEADER',     None                                       ],
        [ 'space_map',            'DMU_OT_SPACE_MAP',            None                                       ],
        [ 'intent_log',           'DMU_OT_INTENT_LOG',           None                                       ],
        [ 'dnode',                'DMU_OT_DNODE',                None                                       ],
        [ 'objset',               'DMU_OT_OBJSET',               None                                       ],
        [ 'dsl_dir',              'DMU_OT_DSL_DIR',              None                                       ],
        [ 'dsl_dir_child_map',    'DMU_OT_DSL_DIR_CHILD_MAP',    None                                       ],
        [ 'dsl_ds_snap_map',      'DMU_OT_DSL_DS_SNAP_MAP',      None                                       ],
        [ 'dsl_props',            'DMU_OT_DSL_PROPS',            None                                       ],
        [ 'dsl_dataset',          'DMU_OT_DSL_DATASET',          None                                       ],
        [ 'znode',                'DMU_OT_ZNODE',                None                                       ],
        [ 'oldacl',               'DMU_OT_OLDACL',               None                                       ],
        [ 'plain_file_contents',  'DMU_OT_PLAIN_FILE_CONTENTS',  None                                       ],
        [ 'directory_contents',   'DMU_OT_DIRECTORY_CONTENTS',   None                                       ],
        [ 'master_node',          'DMU_OT_MASTER_NODE',          None                                       ],
        [ 'unlinked_set',         'DMU_OT_UNLINKED_SET',         None                                       ],
        [ 'zvol',                 'DMU_OT_ZVOL',                 None                                       ],
        [ 'zvol_prop',            'DMU_OT_ZVOL_PROP',            None                                       ],
        [ 'plain_other',          'DMU_OT_PLAIN_OTHER',          None                                       ],
        [ 'uint64_other',         'DMU_OT_UINT64_OTHER',         None                                       ],
        [ 'zap_other',            'DMU_OT_ZAP_OTHER',            None                                       ],
        [ 'error_log',            'DMU_OT_ERROR_LOG',            None                                       ],
        [ 'spa_history',          'DMU_OT_SPA_HISTORY',          None                                       ],
        [ 'spa_history_offsets',  'DMU_OT_SPA_HISTORY_OFFSETS',  None                                       ],
        [ 'pool_props',           'DMU_OT_POOL_PROPS',           None                                       ],
        [ 'dsl_perms',            'DMU_OT_DSL_PERMS',            None                                       ],
        [ 'acl',                  'DMU_OT_ACL',                  None                                       ],
        [ 'sysacl',               'DMU_OT_SYSACL',               None                                       ],
        [ 'fuid',                 'DMU_OT_FUID',                 None                                       ],
        [ 'fuid_size',            'DMU_OT_FUID_SIZE',            None                                       ],
        [ 'next_clones',          'DMU_OT_NEXT_CLONES',          None                                       ],
        [ 'scan_queue',           'DMU_OT_SCAN_QUEUE',           None                                       ],
        [ 'usergroup_used',       'DMU_OT_USERGROUP_USED',       None                                       ],
        [ 'usergroup_quota',      'DMU_OT_USERGROUP_QUOTA',      None                                       ],
        [ 'userrefs',             'DMU_OT_USERREFS',             None                                       ],
        [ 'ddt_zap',              'DMU_OT_DDT_ZAP',              None                                       ],
        [ 'ddt_stats',            'DMU_OT_DDT_STATS',            None                                       ],
        [ 'sa',                   'DMU_OT_SA',                   None                                       ],
        [ 'sa_master_node',       'DMU_OT_SA_MASTER_NODE',       None                                       ],
        [ 'sa_attr_registration', 'DMU_OT_SA_ATTR_REGISTRATION', None                                       ],
        [ 'sa_attr_layouts',      'DMU_OT_SA_ATTR_LAYOUTS',      None                                       ],
        [ 'scan_xlate',           'DMU_OT_SCAN_XLATE',           None                                       ],
        [ 'dedup',                'DMU_OT_DEDUP',                None                                       ],
        [ 'deadlist',             'DMU_OT_DEADLIST',             None                                       ],
        [ 'deadlist_hdr',         'DMU_OT_DEADLIST_HDR',         None                                       ],
        [ 'dsl_clones',           'DMU_OT_DSL_CLONES',           None                                       ],
        [ 'bpobj_subobj',         'DMU_OT_BPOBJ_SUBOBJ',         None                                       ],
        [ 'numtypes',             'DMU_OT_NUMTYPES',             None                                       ],
        [ 'uint8_data',           'DMU_OTN_UINT8_DATA',          DMU_OT(DMU_BSWAP_UINT8, B_FALSE, B_FALSE)  ],
        [ 'uint8_metadata',       'DMU_OTN_UINT8_METADATA',      DMU_OT(DMU_BSWAP_UINT8, B_TRUE, B_FALSE)   ],
        [ 'uint16_data',          'DMU_OTN_UINT16_DATA',         DMU_OT(DMU_BSWAP_UINT16, B_FALSE, B_FALSE) ],
        [ 'uint16_metadata',      'DMU_OTN_UINT16_METADATA',     DMU_OT(DMU_BSWAP_UINT16, B_TRUE, B_FALSE)  ],
        [ 'uint32_data',          'DMU_OTN_UINT32_DATA',         DMU_OT(DMU_BSWAP_UINT32, B_FALSE, B_FALSE) ],
        [ 'uint32_metadata',      'DMU_OTN_UINT32_METADATA',     DMU_OT(DMU_BSWAP_UINT32, B_TRUE, B_FALSE)  ],
        [ 'uint64_data',          'DMU_OTN_UINT64_DATA',         DMU_OT(DMU_BSWAP_UINT64, B_FALSE, B_FALSE) ],
        [ 'uint64_metadata',      'DMU_OTN_UINT64_METADATA',     DMU_OT(DMU_BSWAP_UINT64, B_TRUE, B_FALSE)  ],
        [ 'zap_data',             'DMU_OTN_ZAP_DATA',            DMU_OT(DMU_BSWAP_ZAP, B_FALSE, B_FALSE)    ],
        [ 'zap_metadata',         'DMU_OTN_ZAP_METADATA',        DMU_OT(DMU_BSWAP_ZAP, B_TRUE, B_FALSE)     ],
        [ 'uint8_enc_data',       'DMU_OTN_UINT8_ENC_DATA',      DMU_OT(DMU_BSWAP_UINT8, B_FALSE, B_TRUE)   ],
        [ 'uint8_enc_metadata',   'DMU_OTN_UINT8_ENC_METADATA',  DMU_OT(DMU_BSWAP_UINT8, B_TRUE, B_TRUE)    ],
        [ 'uint16_enc_data',      'DMU_OTN_UINT16_ENC_DATA',     DMU_OT(DMU_BSWAP_UINT16, B_FALSE, B_TRUE)  ],
        [ 'uint16_enc_metadata',  'DMU_OTN_UINT16_ENC_METADATA', DMU_OT(DMU_BSWAP_UINT16, B_TRUE, B_TRUE)   ],
        [ 'uint32_enc_data',      'DMU_OTN_UINT32_ENC_DATA',     DMU_OT(DMU_BSWAP_UINT32, B_FALSE, B_TRUE)  ],
        [ 'uint32_enc_metadata',  'DMU_OTN_UINT32_ENC_METADATA', DMU_OT(DMU_BSWAP_UINT32, B_TRUE, B_TRUE)   ],
        [ 'uint64_enc_data',      'DMU_OTN_UINT64_ENC_DATA',     DMU_OT(DMU_BSWAP_UINT64, B_FALSE, B_TRUE)  ],
        [ 'uint64_enc_metadata',  'DMU_OTN_UINT64_ENC_METADATA', DMU_OT(DMU_BSWAP_UINT64, B_TRUE, B_TRUE)   ],
        [ 'zap_enc_data',         'DMU_OTN_ZAP_ENC_DATA',        DMU_OT(DMU_BSWAP_ZAP, B_FALSE, B_TRUE)     ],
        [ 'zap_enc_metadata',     'DMU_OTN_ZAP_ENC_METADATA',    DMU_OT(DMU_BSWAP_ZAP, B_TRUE, B_TRUE)      ],
    ]

@EnumType
class ZioCkSumType(object):
    '''Imported from C-Enum: enum zio_checksum'''
    TABLE = [
        [ 'inherit',     'ZIO_CHECKSUM_INHERIT',       0    ],
        [ 'on',          'ZIO_CHECKSUM_ON',            None ],
        [ 'off',         'ZIO_CHECKSUM_OFF',           None ],
        [ 'label',       'ZIO_CHECKSUM_LABEL',         None ],
        [ 'gang_header', 'ZIO_CHECKSUM_GANG_HEADER',   None ],
        [ 'zilog',       'ZIO_CHECKSUM_ZILOG',         None ],
        [ 'flether_2',   'ZIO_CHECKSUM_FLETCHER_2',    None ],
        [ 'flether_4',   'ZIO_CHECKSUM_FLETCHER_4',    None ],
        [ 'sha256',      'ZIO_CHECKSUM_SHA256',        None ],
        [ 'zilog2',      'ZIO_CHECKSUM_ZILOG2',        None ],
        [ 'noparity',    'ZIO_CHECKSUM_NOPARITY',      None ],
        [ 'sha512',      'ZIO_CHECKSUM_SHA512',        None ],
        [ 'skein',       'ZIO_CHECKSUM_SKEIN',         None ],
        [ 'edonr',       'ZIO_CHECKSUM_EDONR',         None ],
        [ 'blake3',      'ZIO_CHECKSUM_BLAKE3',        None ],
    ]

@EnumType
class DNF(object):
    '''DNF is dnode-flag'''
    TABLE = [
        [ 'used_bytes',            'DNODE_FLAG_USED_BYTES',            (1 << 0) ],
        [ 'userused_accounted',    'DNODE_FLAG_USERUSED_ACCOUNTED',    (1 << 1) ],
        [ 'crypt_portable',        'DNODE_CRYPT_PORTABLE_FLAGS_MASK',  (1 << 2) ],
        [ 'spill_blkptr',          'DNODE_FLAG_SPILL_BLKPTR',          (1 << 2) ],
        [ 'userobjused_accounted', 'DNODE_FLAG_USEROBJUSED_ACCOUNTED', (1 << 3) ],
    ]
    
    def has(self, flag):
        if (int(self) & flag) != 0:
            return True
        else:
            return False

class DNodePhys(CStruct):
    @property
    def blksz(self):
        return int(512 * self.dn_datablkszsec)
    
    @property
    def indblksz(self):
        return int(1 << self.dn_indblkshift)
    
    blkptr_conv = BlkPtr.convert_method(count=1)
    
    STRUCT_NAME = 'dnode_phys_t'
    FIELDS = [
        [ 'dn_type',           1, 'u8',        'str' ],
        [ 'dn_indblkshift',    1, 'u8',        'str' ],
        [ 'dn_nlevels',        1, 'u8',        'str' ],
        [ 'dn_nblkptr',        1, 'u8',        'str' ],
        [ 'dn_bonustype',      1, 'u8',        'str' ],
        [ 'dn_checksum',       1, 'u8',        'str' ],
        [ 'dn_compress',       1, 'u8',        'str' ],
        [ 'dn_flags',          1, 'u8',        'hex' ], # DNFT.* or DNODE_FLAG_*
        [ 'dn_datablkszsec',   2, 'u16',       'str' ],
        [ 'dn_bonuslen',       2, 'u16',       'str' ],
        [ 'dn_extra_slots',    1, 'u8',        'str' ],
        [ 'dn_pad2',           3, 'u8.array',  'str' ],
        [ 'dn_maxblkid',       8, 'u64',       'str' ],
        [ 'dn_used',           8, 'u64',       'str' ],
        [ 'dn_pad3',          32, 'u64.array', 'str' ],
        [ 'dn_blkptr',       128, blkptr_conv, '--'  ],
        [ 'dn_bonus',        192, 'SKIP',      '--'  ], # the size changable
        [ 'dn_spill',        128, 'SKIP',      '--'  ],
    ]
    
    # 
    # The tail region is 448 bytes for a 512 byte dnode, and
    # correspondingly larger for larger dnode sizes. The spill
    # block pointer, when present, is always at the end of the tail
    # region. There are three ways this space may be used, using
    # a 512 byte dnode for this diagram:
    # 
    # 0       64      128     192     256     320     384     448 (offset)
    # +---------------+---------------+---------------+-------+
    # | dn_blkptr[0]  | dn_blkptr[1]  | dn_blkptr[2]  | /     |
    # +---------------+---------------+---------------+-------+
    # | dn_blkptr[0]  | dn_bonus[0..319]                      |
    # +---------------+-----------------------+---------------+
    # | dn_blkptr[0]  | dn_bonus[0..191]      | dn_spill      |
    # +---------------+-----------------------+---------------+
    #
    
    def _do_init(self, bytes):
        assert(len(bytes) == self.sizeof())
        self.set_fields(bytes)
        
        assert(self.dn_nblkptr >= 1)
        assert(len(self.dn_blkptr) == 1)
        
        blkptr_sz = BlkPtr.sizeof()
        if self.dn_nblkptr > 1:
            off = self.offsetof('dn_blkptr')
            self.dn_blkptr += [
                BlkPtr(bytes[off:off+i*blkptr_sz])
                for i in range(self.dn_nblkptr)[1:]
            ]
        else:
            bonus_off = self.offsetof('dn_bonus')
            if DNF.spill_blkptr.has(dn_flags):
                self.dn_bonus = bytearray(bytes[bonus_off:bonus_off+192])
                spill_off = self.offsetof('dn_spill')
                self.dn_spill = BlkPtr(bytes[spill_off:])
            else:
                self.dn_bonus = bytearray(bytes[bonus_off:bonus_off+320])
        
        for blkptr in self.dn_blkptr:
            assert(blkptr.endian == self.endian)
DNODE_PHYS_LEN = DNodePhys.sizeof()

class ZilHdr(CStruct):
    STRUCT_NAME = 'zil_header_t'
    FIELDS = [
        [ 'zh_claim_txg',     8, 'u64',        'str' ],
        [ 'zh_replay_seq',    8, 'u64',        'str' ],
        [ 'zh_log',         128, BlkPtr,       'str' ],
        [ 'zh_claim_blk_seq', 8, 'u64',        'str' ],
        [ 'zh_flags',         8, 'u64',        'str' ],
        [ 'zh_claim_lr_seq',  8, 'u64',        'str' ],
        [ 'zh_pad',          24, 'u64.array',  'str' ],
    ]
ZIL_HDR_LEN = ZilHdr.sizeof()

class ObjSetPhys(CStruct):
    OS_PAD0_LEN = 2048 - DNODE_PHYS_LEN*3 - ZIL_HDR_LEN - 2*8 - 2*32
    OS_PAD1_LEN = 4096 - 2048 - DNODE_PHYS_LEN
    
    STRUCT_NAME = 'objset_phys_t'
    FIELDS = [
        [ 'os_meta_dnode',        DNODE_PHYS_LEN, DNodePhys,    '<dnode>'  ],
        [ 'os_zil_header',        ZIL_HDR_LEN,    ZilHdr,       '<zilhdr>' ],
        [ 'os_type',              8,              'u64',        'str'      ],
        [ 'os_flags',             8,              'u64',        'hex'      ],
        [ 'os_portable_mac',      32,             'u8.array',   '<mac>'    ],
        [ 'os_local_mac',         32,             'u8.array',   '<mac>'    ],
        [ 'os_pad0',              OS_PAD0_LEN,    'SKIP',       '--'       ],
        [ 'os_userused_dnode',    DNODE_PHYS_LEN, 'SKIP',       '--'       ],
        [ 'os_groupused_dnode',   DNODE_PHYS_LEN, 'SKIP',       '--'       ],
        [ 'os_projectused_dnode', DNODE_PHYS_LEN, 'SKIP',       '--'       ],
        [ 'os_pad1',              OS_PAD1_LEN,    'SKIP',       '--'       ],
    ]
    
    def _do_init(self, bytes):
        self.set_fields(bytes)
        # TODO: resolve fields: os_<user|group|project>used_dnode
