# -*- coding:utf-8 -*-

from . import core

class Compressor(object):
    '''Usage:
       1. compr_data = Compressor.<algorithm>.compress(usr_data)
       2. usr_data = Compressor.<algorithm>.decompress(compr_data)
       3. Algorithm options [lzjb, gzip_<1~9>, lz4]
       4. Example: Compressor.lz4.compress(bytearray(1024))
    '''
    ALGORITHM_TABLE = [
        [  0, 'ZIO_COMPRESS_INHERIT', 'inherit', False ],
        [  1, 'ZIO_COMPRESS_ON',      'on',      False ],
        [  2, 'ZIO_COMPRESS_OFF',     'off',     False ],
        [  3, 'ZIO_COMPRESS_LZJB',    'lzjb',    True  ],
        [  4, 'ZIO_COMPRESS_EMPTY',   'empty',   False ],
        [  5, 'ZIO_COMPRESS_GZIP_1',  'gzip_1',  True  ],
        [  6, 'ZIO_COMPRESS_GZIP_2',  'gzip_2',  True  ],
        [  7, 'ZIO_COMPRESS_GZIP_3',  'gzip_3',  True  ],
        [  8, 'ZIO_COMPRESS_GZIP_4',  'gzip_4',  True  ],
        [  9, 'ZIO_COMPRESS_GZIP_5',  'gzip_5',  True  ],
        [ 10, 'ZIO_COMPRESS_GZIP_6',  'gzip_6',  True  ],
        [ 11, 'ZIO_COMPRESS_GZIP_7',  'gzip_7',  True  ],
        [ 12, 'ZIO_COMPRESS_GZIP_8',  'gzip_8',  True  ],
        [ 13, 'ZIO_COMPRESS_GZIP_9',  'gzip_9',  True  ],
        [ 14, 'ZIO_COMPRESS_ZLE',     'zle',     True  ],
        [ 15, 'ZIO_COMPRESS_LZ4',     'lz4',     True  ],
        [ 16, 'ZIO_COMPRESS_ZSTD',    'zstd',    False ],
    ]
    
    @classmethod
    def ls(cls):
        keylen = max([len(alg[2]) for alg in cls.ALGORITHM_TABLE])
        print('\n'.join([
            '%-*s : %2d' % (keylen,alg[2],alg[0])
            for alg in cls.ALGORITHM_TABLE
        ]))
    
    @classmethod
    def get(cls, key):
        if isinstance(key,str) and key in cls.name_table:
            return cls.name_table[key]
        else:
            try:
                return cls.value_table[int(key)]
            except:
                return None
    
    def compress(self, usr_data):
        self.__check_supported()
        
        mv_usr = memoryview(usr_data)
        out_buffer = memoryview(bytearray(len(mv_usr)-1))
        out_len = core.compress(self.enum_value, mv_usr, out_buffer)
        
        return bytearray(out_buffer[:out_len])
    
    def decompress(self, compressed_data, usr_data_length):
        self.__check_supported()
        
        mv_compr = memoryview(compressed_data)
        assert(usr_data_length > len(mv_compr))
        usr_data = memoryview(bytearray(usr_data_length))
        core.decompress(self.enum_value, usr_data, mv_compr)
        
        return bytearray(usr_data)
    
    name_table,value_table = {},{}
    
    def __init__(self, name, enum_name, enum_value, supported):
        self.name = name
        self.enum_name = enum_name
        self.enum_value = enum_value
        self.supported = supported
    
    def __check_supported(self):
        if not self.supported:
            raise Exception('%s is not supported' % str(compr_type))
    
    def __str__(self):
        return self.name
    __repr__ = __str__
    
    @classmethod
    def register(cls):
        if cls.name_table and cls.value_table:
            return
        
        cls.name_table,cls.value_table = {},{}
        for alg in cls.ALGORITHM_TABLE:
            enum_value,enum_name,name,supported=alg
            inst = cls(
                name       = name,
                enum_name  = enum_name,
                enum_value = enum_value,
                supported  = supported
            )
            cls.name_table[name] = cls.name_table[enum_name] = inst
            cls.value_table[enum_value] = inst
            setattr(cls, name, inst)

Compressor.register()
