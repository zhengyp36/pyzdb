# -*- coding:utf-8 -*-

from . import core

class Compressor(object):
    def __init__(self, compr_type):
        if compr_type.supported:
            self.compr_type = compr_type
        else:
            raise Exception('%s is not supported' % str(compr_type))
    
    def compress(self, usr_data):
        mv_usr = memoryview(usr_data)
        
        out_buffer = memoryview(bytearray(len(mv_usr)-1))
        out_len = core.compress(self.compr_type.value, mv_usr, out_buffer)
        return bytearray(out_buffer[:out_len])
    
    def decompress(self, compressed_data, usr_data_length):
        mv_compr = memoryview(compressed_data)
        assert(usr_data_length > len(mv_compr))
        
        usr_data = memoryview(bytearray(usr_data_length))
        core.decompress(self.compr_type.value, usr_data, mv_compr)
        return bytearray(usr_data)

class CompressType(object):
    def __init__(self, name, value, supported=True):
        self._name = name
        self._value = int(value)
        self._supported = supported
        self._register()
    
    def __str__(self):
        return self._name
    __repr__ = __str__
    
    @property
    def value(self):
        return self._value
    
    @property
    def supported(self):
        return self._supported
    
    NAME_TABLE = {}
    VALUE_TABLE = {}
    
    def _register(self):
        assert(self._name not in self.NAME_TABLE)
        assert(self._value not in self.VALUE_TABLE)
        self.NAME_TABLE[self._name] = self
        self.VALUE_TABLE[self._value] = self
    
    @classmethod
    def get(cls, key):
        if isinstance(key,str) and key in cls.NAME_TABLE:
            return cls.NAME_TABLE[key]
        try:
            return cls.VALUE_TABLE[int(key)]
        except:
            return None

ZIO_COMPRESS_INHERIT = CompressType('ZIO_COMPRESS_INHERIT', 0, supported=False)
ZIO_COMPRESS_ON      = CompressType('ZIO_COMPRESS_ON',      1, supported=False)
ZIO_COMPRESS_OFF     = CompressType('ZIO_COMPRESS_OFF',     2, supported=False)
ZIO_COMPRESS_LZJB    = CompressType('ZIO_COMPRESS_LZJB',    3)
ZIO_COMPRESS_EMPTY   = CompressType('ZIO_COMPRESS_EMPTY',   4, supported=False)
ZIO_COMPRESS_GZIP_1  = CompressType('ZIO_COMPRESS_GZIP_1',  5)
ZIO_COMPRESS_GZIP_2  = CompressType('ZIO_COMPRESS_GZIP_2',  6)
ZIO_COMPRESS_GZIP_3  = CompressType('ZIO_COMPRESS_GZIP_3',  7)
ZIO_COMPRESS_GZIP_4  = CompressType('ZIO_COMPRESS_GZIP_4',  8)
ZIO_COMPRESS_GZIP_5  = CompressType('ZIO_COMPRESS_GZIP_5',  9)
ZIO_COMPRESS_GZIP_6  = CompressType('ZIO_COMPRESS_GZIP_6', 10)
ZIO_COMPRESS_GZIP_7  = CompressType('ZIO_COMPRESS_GZIP_7', 11)
ZIO_COMPRESS_GZIP_8  = CompressType('ZIO_COMPRESS_GZIP_8', 12)
ZIO_COMPRESS_GZIP_9  = CompressType('ZIO_COMPRESS_GZIP_9', 13)
ZIO_COMPRESS_ZLE     = CompressType('ZIO_COMPRESS_ZLE',    14)
ZIO_COMPRESS_LZ4     = CompressType('ZIO_COMPRESS_LZ4',    15)
ZIO_COMPRESS_ZSTD    = CompressType('ZIO_COMPRESS_ZSTD',   16, supported=False)
