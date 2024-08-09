# -*- coding:utf-8 -*-

from . import core
from .utils import EnumType

@EnumType
class Compressor(object):
    '''Usage:
       1. compr_data = Compressor.<algorithm>.compress(usr_data)
       2. usr_data = Compressor.<algorithm>.decompress(compr_data)
       3. Algorithm options [lzjb, gzip_<1~9>, lz4]
       4. Example: Compressor.lz4.compress(bytearray(1024))
    '''
    
    TABLE = [
        [ 'inherit','ZIO_COMPRESS_INHERIT',  0, False ],
        [ 'on',     'ZIO_COMPRESS_ON',       1, False ],
        [ 'off',    'ZIO_COMPRESS_OFF',      2, False ],
        [ 'lzjb',   'ZIO_COMPRESS_LZJB',     3, True  ],
        [ 'empty',  'ZIO_COMPRESS_EMPTY',    4, False ],
        [ 'gzip_1', 'ZIO_COMPRESS_GZIP_1',   5, True  ],
        [ 'gzip_2', 'ZIO_COMPRESS_GZIP_2',   6, True  ],
        [ 'gzip_3', 'ZIO_COMPRESS_GZIP_3',   7, True  ],
        [ 'gzip_4', 'ZIO_COMPRESS_GZIP_4',   8, True  ],
        [ 'gzip_5', 'ZIO_COMPRESS_GZIP_5',   9, True  ],
        [ 'gzip_6', 'ZIO_COMPRESS_GZIP_6',  10, True  ],
        [ 'gzip_7', 'ZIO_COMPRESS_GZIP_7',  11, True  ],
        [ 'gzip_8', 'ZIO_COMPRESS_GZIP_8',  12, True  ],
        [ 'gzip_9', 'ZIO_COMPRESS_GZIP_9',  13, True  ],
        [ 'zle',    'ZIO_COMPRESS_ZLE',     14, True  ],
        [ 'lz4',    'ZIO_COMPRESS_LZ4',     15, True  ],
        [ 'zstd',   'ZIO_COMPRESS_ZSTD',    16, False ],
    ]
    
    def __init__(self, entry):
        # 'entry' is an elemement of self.TABLE
        self.supported = entry[3]
    
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
    
    def __check_supported(self):
        if not self.supported:
            raise Exception('%s<%s,%d> is unsupported' % (
                str(self), repr(self), int(self)
            ))
