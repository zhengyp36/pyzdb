# -*- coding:utf-8 -*-
# zctypes is zfs-C-Types

from .utils import *

class DVA(CStruct):
    STRUCT_NAME = 'dva_t'
    FIELDS = [['dva_word', 16, 'u64.array', 'str']]
    
    def _validate(self):
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
    
    def _set_endian(self, bytes, endian):
        offset = self.offsetof('blk_prop') + 7
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
    FIELDS_INITED = False
    
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
