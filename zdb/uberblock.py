# -*- coding:utf-8 -*-

from . import utils
from . import dmu

class UberBlock(utils.CStruct):
    FIELDS,SIZE_U64 = [],0
    UBERBLOCK_MAGIC = 0x00bab10c # oo-ba-block
    
    @classmethod
    def initFields(cls):
        if not cls.FIELDS:
            conv_magic   = lambda d : utils.HexInt(d[0])
            conv_blkptr  = lambda d : dmu.BlkPtr.from_ints(d)
            conv_int     = lambda d : int(d[0])
            
            make = lambda name,szInU64,convert,formatter : (cls.FIELDS.append(
                utils.CStructField(name,szInU64,convert,formatter)
            ))
            
            make('ub_magic',            1, conv_magic,  str  )
            make('ub_version',          1, conv_int,    str  )
            make('ub_txg',              1, conv_int,    str  )
            make('ub_guid_sum',         1, conv_int,    hex  )
            make('ub_timestamp',        1, conv_int,    hex  )
            make('ub_rootbp',          16, conv_blkptr, '--' )
            make('ub_software_version', 1, conv_int,    str  )
            make('ub_mmp_magic',        1, conv_magic,  str  )
            make('ub_mmp_delay',        1, conv_int,    str  )
            make('ub_mmp_config',       1, conv_int,    str  )
            make('ub_checkpoint_txg',   1, conv_int,    str  )
            
            cls.SIZE_U64 = sum([field.szInU64 for field in cls.FIELDS])
    
    def __init__(self, bins=None, ints=None, endian='little'):
        super(type(self),self).__init__(bins=bins, ints=ints, endian=endian)
        self.initFields()
        self.label_index = self.uberblock_index = -1
        
        if ints is None:
            if bins is None:
                data = [0] * self.SIZE_U64
                self.endian = None # the uberblock not initialized
                data[0] = self.UBERBLOCK_MAGIC
            else:
                sz = len(bins) // 8
                assert(sz >= self.SIZE_U64)
                
                self.endian = None
                for endian in ['little','big']:
                    magic = utils.read_u64(bins, endian=endian, count=1)[0]
                    if magic == self.UBERBLOCK_MAGIC:
                        self.endian = endian
                        break
                
                assert(self.endian is not None)
                data = utils.read_u64(bins, endian=self.endian,
                    count=self.SIZE_U64)
        else:
            data = ints # integer array
            self.endian = endian
            assert(len(data) >= self.SIZE_U64)
        
        self.setattrs_u64(data)
    
    def __cmp(self, other):
        return self.ub_txg - other.ub_txg
    
    def __lt__(self, other):
        return self.__cmp(other) < 0
    
    def __le__(self, other):
        return self.__cmp(other) <= 0
    
    def __gt__(self, other):
        return self.__cmp(other) > 0
    
    def __ge__(self, other):
        return self.__cmp(other) >= 0
    
    def __eq__(self, other):
        return self.__cmp(other) == 0
    
    def __ne__(self, other):
        return self.__cmp(other) != 0
