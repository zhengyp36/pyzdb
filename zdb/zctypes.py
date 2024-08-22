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
        
        if self.embed:
            self._copy_embeded_data(bytes)
    
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
    
    def _copy_embeded_data(self, bytes):
        self.bytes = bytearray(self.sizeof())
        array = memoryview(self.bytes)
        
        src,dst = 0,0
        for entry in self.FIELDS:
            name,sz = entry[0:2]
            if name not in ['blk_prop','blk_birth']:
                array[dst:dst+sz] = bytes[src:src+sz]
                dst += sz
            src += sz
    
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
    
    def diskLocation(self, shift=9):
        if not self.embed:
            dva_arr,idx = [],0
            for dva in self.blk_dva:
                if dva.asize:
                    dva_arr.append({
                        'index'  : idx,
                        'vdev'   : dva.vdev,
                        'offset' : dva.offset << shift,
                        'asize'  : dva.asize << shift,
                        'gang'   : dva.gang,
                        'grid'   : dva.grid,
                    })
                idx += 1
        else:
            shift = 0
            dva_arr = None
        
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
BLKPTR_SIZE = BlkPtr.sizeof()

class UberBlock(CStruct):
    STRUCT_NAME = 'uberblock_t'
    FIELDS = [
        [ 'ub_magic',            8, 'u64',  'magic32' ],
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
            raise MagicError(self)
        
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
        assert(self.dn_extra_slots == 0)
        
        if self.dn_nblkptr > 1:
            sz = BlkPtr.sizeof()
            bp = bytes[self.offsetof('dn_blkptr'):]
            self.dn_blkptr += [
                BlkPtr(bp[i*sz:i*sz+sz])
                for i in range(self.dn_nblkptr)[1:]
            ]
        
        if self.dn_bonuslen > 0:
            bonus_off = (self.offsetof('dn_bonus') +
                (self.dn_nblkptr - 1) * BLKPTR_SIZE)
            self.dn_bonus = bytearray(bytes[
                bonus_off : bonus_off+self.dn_bonuslen
            ])
        
        if DNF.spill_blkptr.has(self.dn_flags):
            spill_off = self.offsetof('dn_spill')
            self.dn_spill = BlkPtr(bytes[spill_off:])
        
        for blkptr in self.dn_blkptr:
            assert(blkptr.is_hole or blkptr.endian == self.endian)
DNODE_PHYS_LEN = DNodePhys.sizeof()

# TODO: Explore the internal workings of ZIL in more detail
class ZilHdr(CStruct):
    STRUCT_NAME = 'zil_header_t'
    FIELDS = [
        [ 'zh_claim_txg',     8, 'u64',        'str'      ],
        [ 'zh_replay_seq',    8, 'u64',        'str'      ],
        [ 'zh_log',         128, BlkPtr,       '<blkptr>' ],
        [ 'zh_claim_blk_seq', 8, 'u64',        'str'      ],
        [ 'zh_flags',         8, 'u64',        'str'      ],
        [ 'zh_claim_lr_seq',  8, 'u64',        'str'      ],
        [ 'zh_pad',          24, 'u64.array',  'str'      ],
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

@EnumType
class ZBT(object):
    '''Imported from C-Macro: ZBT_* and ZBT is ZapBlkType'''
    TABLE = [
        [ 'micro',  'ZBT_MICRO',  ((1 << 63) + 3) ],
        [ 'header', 'ZBT_HEADER', ((1 << 63) + 1) ],
        [ 'leaf',   'ZBT_LEAF',   ((1 << 63) + 0) ],
    ]

@EnumType
class MatchType(object):
    '''Imported from C-Enum matchtype_t defined in zap.h'''
    TABLE = [
        [ 'normalize', 'MT_NORMALIZE',  (1 << 0) ],
        [ 'matchcase', 'MT_MATCH_CASE', (1 << 1) ],
    ]

@EnumType
class ZapF(object):
    '''Imported from C-Enum zfs_zap_flags_t or zap_flags_t'''
    TABLE = [
        [ 'hash64',  'ZAP_FLAG_HASH64',         (1 << 0) ],
        [ 'u64key',  'ZAP_FLAG_UINT64_KEY',     (1 << 1) ],
        [ 'prehash', 'ZAP_FLAG_PRE_HASHED_KEY', (1 << 2) ],
    ]

@EnumType
class ZLF(object):
    '''Imported from C-Macro ZLF_ENTRIES_CDSORTED'''
    TABLE = [
        [ 'cdsorted', 'ZLF_ENTRIES_CDSORTED', (1 << 0) ],
    ]

@EnumType
class ZapChunkType(object):
    '''Imported from C-Macro zap_chunk_type_t'''
    TABLE = [
        [ 'free',  'ZAP_CHUNK_FREE',  253 ],
        [ 'entry', 'ZAP_CHUNK_ENTRY', 252 ],
        [ 'array', 'ZAP_CHUNK_ARRAY', 251 ],
    ]

class MZapEnt(CStruct):
    STRUCT_NAME = 'mzap_ent_phys_t'
    FIELDS = [
        [ 'mze_value', 8, 'u64',  'str' ],
        [ 'mze_cd',    4, 'u32',  'str' ],
        [ 'mze_pad',   2, 'SKIP', 'str' ],
        [ 'mze_name', 50, 'str',  'str' ],
        [ 'mze_hash',  0, 'SKIP', 'str' ],
    ]

class MZapPhys(CStruct):
    STRUCT_NAME = 'mzap_phys_t'
    FIELDS = [
        [ 'mz_block_type', 8, 'u64',       'magic64' ], # ZBT
        [ 'mz_salt',       8, 'u64',       'str'     ],
        [ 'mz_normflags',  8, 'u64',       'str'     ],
        [ 'mz_pad',       40, 'u64.array', 'str'     ],
        [ 'mz_chunk',     64, 'SKIP',      '--'      ],
    ]
    
    def _do_init(self, bytes):
        self.set_fields(bytes)
        assert(self.mz_block_type == int(ZBT.micro))
        
        st_sz, sz = self.sizeof(), self.FIELDS[self.indexof('mz_chunk')][1]
        count = (len(bytes) - st_sz) // sz + 1
        
        self.mz_chunk,self.items = [],{}
        for chunk in MZapEnt.convert_method(count=count)(bytes[st_sz-sz:]):
            if chunk.mze_name != '':
                chunk.mze_hash = Crc64Poly.hash(chunk.mze_name, self.mz_salt)
                self.mz_chunk.append(chunk)
                self.items[chunk.mze_name] = chunk
        
        self.mz_chunk.sort(key=lambda chunk : chunk.mze_hash)
        self.is_micro = True

class ZapTblPhys(CStruct):
    '''Imported from C-Struct zap_table_phys_t in zap_phys_t'''
    FIELDS = [
        [ 'zt_blk',         8, 'u64', 'str' ],
        [ 'zt_numblks',     8, 'u64', 'str' ],
        [ 'zt_shift',       8, 'u64', 'str' ],
        [ 'zt_nextblk',     8, 'u64', 'str' ],
        [ 'zt_blks_copied', 8, 'u64', 'str' ],
    ]

class ZapPhys(CStruct):
    STRUCT_NAME = 'zap_phys_t'
    FIELDS = [
        [ 'zap_block_type',   8, 'u64',      'magic64'  ], # ZBT
        [ 'zap_magic',        8, 'u64',      'magic64'  ],
        [ 'zap_ptrtbl',      40, ZapTblPhys, '--'       ],
        [ 'zap_freeblk',      8, 'u64',      'str'      ],
        [ 'zap_num_leafs',    8, 'u64',      'str'      ],
        [ 'zap_num_entries',  8, 'u64',      'str'      ],
        [ 'zap_salt',         8, 'u64',      'str'      ],
        [ 'zap_normflags',    8, 'u64',      'str'      ],
        [ 'zap_flags',        8, 'u64',      'str'      ], # ZapF
    ]
    MAGIC = 0x2F52AB2AB # zfs-zap-zap
    
    @classmethod
    def from_bytes(cls, bytes, endian=Endian.default):
        zbt_value = Int.from_bytes(bytes[0:8])
        try:
            zbt = ZBT.from_int(zbt_value)
        except:
            raise MagicError(self, value='INV_ZBT{%x}' % zbt_value)
        
        if zbt == ZBT.header:
            return cls(bytes, endian=endian)
        else:
            return MZapPhys(bytes, endian=endian)
    
    def _do_init(self, bytes):
        self.is_micro = False
        
        zbt_value = Int.from_bytes(bytes[0:8])
        magic_value = Int.from_bytes(bytes[8:16])
        
        try:
            zbt = ZBT.from_int(zbt_value)
        except:
            raise MagicError(self, value='INV_ZBT{%x}' % zbt_value)
        
        if zbt_value != int(ZBT.header):
            raise Unsupported(self,
                value='INV_ZBT_HEADER{%x}' % zbt_value)
        
        self.set_fields(bytes)
        if self.table_embeded:
            assert(self.zap_ptrtbl.zt_blk == 0)
            # Every entry contains a number of uint64. The size of zap-block
            # is 16KB, and half i.e. 8KB is used for table.
            assert(self.zap_ptrtbl.zt_shift == 10)
            off = len = 8 * (1 << self.zap_ptrtbl.zt_shift)
            self.table = Int.from_bytes_to_list(bytes[off:off+len], int_size=8)
        else:
            self.table = None
    
    @property
    def table_embeded(self):
        assert(not self.is_micro)
        return self.zap_ptrtbl.zt_numblks == 0

class ZapLeafPhys(CStruct):
    STRUCT_NAME = 'zap_leaf_phys_t'
    FIELDS = [
        [ 'l_hdr',   0, 'SKIP', '--' ],
        [ 'l_hash',  0, 'SKIP', '--' ],
        [ 'l_chunk', 0, 'SKIP', '--' ],
    ]
    CHAIN_END = 0xffff
    
    def _do_init(self, bytes):
        self.set_fields(bytes)
        
        self.blksz = len(bytes)
        is_power2 = lambda n : (n&(n-1)) == 0
        assert(is_power2(self.blksz) and self.blksz >= 512)
        
        pos,sz = 0,self.Header.sizeof()
        self.l_hdr = self.Header(bytes[pos:pos+sz], endian=self.endian)
        pos += sz
        
        sz = self.blksz >> 4
        self.l_hash = Int.from_bytes_to_list(bytes[pos:pos+sz],
            int_size=2, endian=self.endian)
        pos += sz
        
        chunks = (self.blksz - pos) // self.Chunk.SIZE
        convert = self.Chunk.convert_method(count=chunks)
        self.l_chunk = convert(bytes[pos:], endian=self.endian)
        
        assert(self.l_hdr.lh_magic == self.Header.MAGIC)
    
    def read(self, id, size=None):
        assert(0 <= id < len(self.l_chunk))
        assert(self.l_chunk[id].l_array.la_type == int(ZapChunkType.array))
        
        array = bytearray(0)
        while id != self.CHAIN_END:
            la = self.l_chunk[id].l_array
            array += la.la_array
            id = la.la_next
        
        if size is None:
            return array
        else:
            assert(size <= len(array))
            return array[:size]
    
    class Header(CStruct):
        STRUCT_NAME = 'struct zap_leaf_header'
        FIELDS = [
            [ 'lh_block_type', 8, 'u64',      'str' ],
            [ 'lh_pad1',       8, 'u64',      'str' ],
            [ 'lh_prefix',     8, 'u64',      'str' ],
            [ 'lh_magic',      4, 'u32',      'str' ],
            [ 'lh_nfree',      2, 'u16',      'str' ],
            [ 'lh_nentries',   2, 'u16',      'str' ],
            [ 'lh_prefix_len', 2, 'u16',      'str' ],
            [ 'lh_freelist',   2, 'u16',      'str' ],
            [ 'lh_flags',      1, 'u8',       'str' ], # ZLF
            [ 'lh_pad2',      11, 'u8.array', '--'  ],
        ]
        MAGIC = 0x2AB1EAF # zap-leaf
    
    class Chunk(CStruct):
        STRUCT_NAME = 'zap_leaf_chunk_t'
        FIELDS = [
            [ 'l_entry', 0, 'SKIP', '--' ],
            [ 'l_array', 0, 'SKIP', '--' ],
            [ 'l_free',  0, 'SKIP', '--' ],
        ]
        SIZE = 24
        
        class Entry(CStruct):
            STRUCT_NAME = 'struct zap_leaf_entry'
            FIELDS = [
                [ 'le_type',          1, 'u8',   'str'     ], # ZapChunkType
                [ 'le_value_intlen',  1, 'u8',   'str'     ],
                [ 'le_next',          2, 'u16',  'str'     ],
                [ 'le_name_chunk',    2, 'u16',  'str'     ],
                [ 'le_name_numints',  2, 'u16',  'str'     ],
                [ 'le_value_chunk',   2, 'u16',  'str'     ],
                [ 'le_value_numints', 2, 'u16',  'str'     ],
                [ 'le_cd',            4, 'u32',  'str'     ],
                [ 'le_hash',          8, 'u64',  'magic64' ],
            ]
        class Array(CStruct):
            STRUCT_NAME = 'struct zap_leaf_array'
            FIELDS = [
                [ 'la_type',   1, 'u8',   'str' ], # ZapChunkType
                [ 'la_array', 21, 'byte', '--'  ],
                [ 'la_next',   2, 'u16',  'str' ],
            ]
        class Free(CStruct):
            STRUCT_NAME = 'struct zap_leaf_free'
            FIELDS = [
                [ 'lf_type',  1, 'u8',   'str' ], # ZapChunkType
                [ 'lf_pad',  21, 'SKIP', '--'  ],
                [ 'lf_next',  2, 'u16',  'str' ],
            ]
        
        def _do_init(self, bytes):
            self.set_fields(bytes)
            
            nt = {
                int(ZapChunkType.entry) : ('l_entry', self.Entry),
                int(ZapChunkType.array) : ('l_array', self.Array),
                int(ZapChunkType.free)  : ('l_free',  self.Free),
            }[Int.from_bytes(bytes[0:1])]
            
            setattr(self, nt[0], nt[1](bytes, self.endian))
        
        @classmethod
        def sizeof(cls, field_def=None):
            return cls.SIZE
        
        def do_format(self, field_def=None, checker=None, keylen=None):
            val = None
            for entry in self.FIELDS:
                val = getattr(self, entry[0])
                if val is not None:
                    break
            return self.STRUCT_NAME + ' -> ' + str(val)

@EnumType
class DDFlag(object):
    '''dsl dir flags'''
    TABLE = [
        [ 'used_breakdown', 'DD_FLAG_USED_BREAKDOWN', (1 << 0) ],
    ]

@EnumType
class DDUsed(object):
    '''dd_used_t'''
    TABLE = [
        [ 'head',       'DD_USED_HEAD',       None ],
        [ 'snap',       'DD_USED_SNAP',       None ],
        [ 'child',      'DD_USED_CHILD',      None ],
        [ 'child_rsrv', 'DD_USED_CHILD_RSRV', None ],
        [ 'refrsrv',    'DD_USED_REFRSRV',    None ],
        [ 'num',        'DD_USED_NUM',        None ],
    ]

class DslDirPhys(CStruct):
    STRUCT_NAME = 'dsl_dir_phys_t'
    FIELDS = [
        [ 'dd_creation_time',      8,                 'u64',       'str' ],
        [ 'dd_head_dataset_obj',   8,                 'u64',       'str' ],
        [ 'dd_parent_obj',         8,                 'u64',       'str' ],
        [ 'dd_origin_obj',         8,                 'u64',       'str' ],
        [ 'dd_child_dir_zapobj',   8,                 'u64',       'str' ],
        [ 'dd_used_bytes',         8,                 'u64',       'str' ],
        [ 'dd_compressed_bytes',   8,                 'u64',       'str' ],
        [ 'dd_uncompressed_bytes', 8,                 'u64',       'str' ],
        [ 'dd_quota',              8,                 'u64',       'str' ],
        [ 'dd_reserved',           8,                 'u64',       'str' ],
        [ 'dd_props_zapobj',       8,                 'u64',       'str' ],
        [ 'dd_deleg_zapobj',       8,                 'u64',       'str' ],
        [ 'dd_flags',              8,                 'u64',       'str' ],
        [ 'dd_used_breakdown',     8*int(DDUsed.num), 'u64.array', 'str' ],
        [ 'dd_clones',             8,                 'u64',       'str' ],
        [ 'dd_pad',                8*13,              'SKIP',      '--'  ],
    ]

class DslDataSetPhys(CStruct):
    STRUCT_NAME = 'dsl_dataset_phys_t'
    FIELDS = [
        [ 'ds_dir_obj',            8, 'u64',       'str'      ],
        [ 'ds_prev_snap_obj',      8, 'u64',       'str'      ],
        [ 'ds_prev_snap_txg',      8, 'u64',       'str'      ],
        [ 'ds_next_snap_obj',      8, 'u64',       'str'      ],
        [ 'ds_snapnames_zapobj',   8, 'u64',       'str'      ],
        [ 'ds_num_children',       8, 'u64',       'str'      ],
        [ 'ds_creation_time',      8, 'u64',       'str'      ],
        [ 'ds_creation_txg',       8, 'u64',       'str'      ],
        [ 'ds_deadlist_obj',       8, 'u64',       'str'      ],
        [ 'ds_referenced_bytes',   8, 'u64',       'str'      ],
        [ 'ds_compressed_bytes',   8, 'u64',       'str'      ],
        [ 'ds_uncompressed_bytes', 8, 'u64',       'str'      ],
        [ 'ds_unique_bytes',       8, 'u64',       'str'      ],
        [ 'ds_fsid_guid',          8, 'u64',       'str'      ],
        [ 'ds_guid',               8, 'u64',       'str'      ],
        [ 'ds_flags',              8, 'u64',       'str'      ],
        [ 'ds_bp',               128, BlkPtr,      '<blkptr>' ],
        [ 'ds_next_clones_obj',    8, 'u64',       'str'      ],
        [ 'ds_props_obj',          8, 'u64',       'str'      ],
        [ 'ds_userrefs_obj',       8, 'u64',       'str'      ],
        [ 'ds_pad',               40, 'u64.array', '--'       ],
    ]

class SaHdrPhys(CStruct):
    layout_detail = lambda val,inst : 'layout.%d.size.%d' % (
        Int(val).bit_field(0,10),
        ((Int(val).bit_field(10,6) << 3)),
    )
    
    STRUCT_NAME = 'sa_hdr_phys_t'
    FIELDS = [
        [ 'sa_magic',       4, 'u32',         'hex' ],
        [ 'sa_layout_info', 2, 'u16', layout_detail ],
        [ 'sa_lengths',     2, 'u16.array',   'str' ],
    ]
    MAGIC = 0x2F505A  # ZFS SA
    
    @property
    def hdrsize(self):
        return Int(self.sa_layout_info).bit_field(10,6) << 3
    
    @property
    def layout_num(self):
        return Int(self.sa_layout_info).bit_field(0,10)
    
    @property
    def attr_buffer(self):
        return self.buffer[self.hdrsize:]
    
    def _do_init(self, bytes):
        self.buffer = memoryview(bytes)
        
        self._endian = None
        for endian in [Endian.little, Endian.big]:
            if Int.from_bytes(self.buffer[0:4], endian=endian) == self.MAGIC:
                self._endian = endian
                break
        if self._endian is None:
            raise MagicError(self)
        
        self.set_fields(self.buffer)
        self.sa_lengths += Int.from_bytes_to_list(
            self.buffer[self.sizeof():self.hdrsize],
            int_size=2
        )

@EnumType
class DT(object):
    '''Imported from C-Enum from dirent.h'''
    TABLE = [
        [ 'unknown', 'DT_UNKNOWN', 0 ],
        [ 'fifo',    'DT_FIFO',    1 ],
        [ 'chr',     'DT_CHR',     2 ],
        [ 'dir',     'DT_DIR',     4 ],
        [ 'blk',     'DT_BLK',     6 ],
        [ 'reg',     'DT_REG',     8 ],
        [ 'lnk',     'DT_LNK',    10 ],
        [ 'sock',    'DT_SOCK',   12 ],
        [ 'wht',     'DT_WHT',    14 ],
    ]

@EnumType
class ACE_TF(object):
    '''ACE_TF is ACE_TYPE_FLAGS defined in acl.h'''
    TABLE = [
        [ 'file_inherit',         'ACE_FILE_INHERIT_ACE',           0x0001 ],
        [ 'dir_inherit',          'ACE_DIRECTORY_INHERIT_ACE',      0x0002 ],
        [ 'no_propagate_inherit', 'ACE_NO_PROPAGATE_INHERIT_ACE',   0x0004 ],
        [ 'inherit_only',         'ACE_INHERIT_ONLY_ACE',           0x0008 ],
        [ 'succ_access',          'ACE_SUCCESSFUL_ACCESS_ACE_FLAG', 0x0010 ],
        [ 'fail_access',          'ACE_FAILED_ACCESS_ACE_FLAG',     0x0020 ],
        [ 'identifier_group',     'ACE_IDENTIFIER_GROUP',           0x0040 ],
        [ 'inherit',              'ACE_INHERITED_ACE',              0x0080 ],
        [ 'owner',                'ACE_OWNER',                      0x1000 ],
        [ 'group',                'ACE_GROUP',                      0x2000 ],
        [ 'everyone',             'ACE_EVERYONE',                   0x4000 ],
    ]
    
    @classmethod
    def is_ogr(cls, flags):
        '''oge is owner-group-everyone'''
        
        owner = int(cls.owner)
        owning_group = int(cls.group) | int(cls.identifier_group)
        everyone = int(cls.everyone)
        
        flags &= owner | everyone | owning_group
        return flags in [owner, everyone, owning_group]

@EnumType
class ACE_TYPE(object):
    TABLE = [
        [ 'allow',          'ACE_ACCESS_ALLOWED_ACE_TYPE',                 0x00 ],
        [ 'deny',           'ACE_ACCESS_DENIED_ACE_TYPE',                  0x01 ],
        [ 'audit',          'ACE_SYSTEM_AUDIT_ACE_TYPE',                   0x02 ],
        [ 'alarm',          'ACE_SYSTEM_ALARM_ACE_TYPE',                   0x03 ],
        [ 'allowed_compnd', 'ACE_ACCESS_ALLOWED_COMPOUND_ACE_TYPE',        0x04 ],
        [ 'allowed_obj',    'ACE_ACCESS_ALLOWED_OBJECT_ACE_TYPE',          0x05 ],
        [ 'denied_obj',     'ACE_ACCESS_DENIED_OBJECT_ACE_TYPE',           0x06 ],
        [ 'audit_obj',      'ACE_SYSTEM_AUDIT_OBJECT_ACE_TYPE',            0x07 ],
        [ 'alarm_obj',      'ACE_SYSTEM_ALARM_OBJECT_ACE_TYPE',            0x08 ],
        [ 'allowed_cb',     'ACE_ACCESS_ALLOWED_CALLBACK_ACE_TYPE',        0x09 ],
        [ 'denied_cb',      'ACE_ACCESS_DENIED_CALLBACK_ACE_TYPE',         0x0A ],
        [ 'allowed_cb_obj', 'ACE_ACCESS_ALLOWED_CALLBACK_OBJECT_ACE_TYPE', 0x0B ],
        [ 'denied_cb_obj',  'ACE_ACCESS_DENIED_CALLBACK_OBJECT_ACE_TYPE',  0x0C ],
        [ 'audit_cb',       'ACE_SYSTEM_AUDIT_CALLBACK_ACE_TYPE',          0x0D ],
        [ 'alarm_cb',       'ACE_SYSTEM_ALARM_CALLBACK_ACE_TYPE',          0x0E ],
        [ 'audit_cb_obj',   'ACE_SYSTEM_AUDIT_CALLBACK_OBJECT_ACE_TYPE',   0x0F ],
        [ 'alarm_cb_obj',   'ACE_SYSTEM_ALARM_CALLBACK_OBJECT_ACE_TYPE',   0x10 ],
    ]
    
    def get_ace_type(self, flags):
        cls = type(self)
        if self in [cls.allowed_obj,cls.denied_obj,cls.audit_obj,cls.alarm_obj]:
            return 'ace_obj'
        
        if (self in [cls.allow,cls.deny]) and ACE_TF.is_ogr(flags):
            return 'ace_hdr'
        else:
            return 'ace'

class ZfsAceHdr(CStruct):
    STRUCT_NAME = 'zfs_ace_hdr_t'
    FIELDS = [
        [ 'z_type',        2, 'u16', 'hex' ],
        [ 'z_flags',       2, 'u16', 'hex' ],
        [ 'z_access_mask', 4, 'u32', 'oct' ],
    ]
    
    # TODO: parse zfs_ace_t & zfs_object_ace_t ...
    FIELDS_FOR_ACE = [
        [ 'z_fuid',        8, 'u64', 'str' ],
    ]
    
    @property
    def type(self):
        return ACE_TYPE.from_int(self.z_type).get_ace_type(self.z_flags)
    
    @classmethod
    def from_bytes(cls, bytes, endian=Endian.default):
        array = []
        
        buffer = memoryview(bytes)
        pos,sz = 0,cls.sizeof()
        
        while pos+sz <= len(buffer):
            hdr = cls(buffer[pos:pos+sz], endian=endian)
            pos += sz
            assert(hdr.type == 'ace_hdr')
            array.append(hdr)
        
        return array

@EnumType
class OST(object):
    '''Imported from C-Enum: dmu_objset_type_t'''
    TABLE = [
        [ 'none',  'DMU_OST_NONE',  None ],
        [ 'meta',  'DMU_OST_META',  None ],
        [ 'zfs',   'DMU_OST_ZFS',   None ],
        [ 'zvol',  'DMU_OST_ZVOL',  None ],
        [ 'other', 'DMU_OST_OTHER', None ],
        [ 'any',   'DMU_OST_ANY',   None ],
    ]

class SpaceMapPhys(CStruct):
    STRUCT_NAME = 'space_map_phys_t'
    FIELDS = [
        [ 'smp_object',       8, 'u64',       'str' ],
        [ 'smp_length',       8, 'u64',       'str' ],
        [ 'smp_alloc',        8, 's64',       'str' ],
        [ 'smp_pad',        5*8, 'u64.array', '--'  ],
        [ 'smp_histogram', 32*8, 'u64.array', '--'  ],
    ]
