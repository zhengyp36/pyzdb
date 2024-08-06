# -*- coding:utf-8 -*-

import sys
import struct

INTEGER_FORMATTER = {1:'B', 2:'H', 4:'I', 8:'Q'}
INTEGER_SIZES = list(INTEGER_FORMATTER.keys())
INTEGER_SIZES.sort()

def int_from_bytes(data, endian='little', signed=False):
    '''Convert bytes data to integer. Return the integer represented by
    the given array of bytes. The argument 'endian' should be 'little' or
    'big'. The function is similar to int.from_bytes which is
    not implemented in Python-2.x
    '''
    
    if len(data) not in INTEGER_SIZES:
        raise ValueError('len(data)=%d, not in %s' % (
            len(data), str(INTEGER_SIZES)))
    
    fmt_sz = INTEGER_FORMATTER[len(data)]
    if signed:
        fmt_sz = fmt_sz.lower()
    
    if endian not in ['little', 'big']:
        raise ValueError("Invalid endian type '%s'" % endian)
    fmt_endian = {'little' : '<', 'big' : '>'}[endian]
    
    return struct.unpack(''.join([fmt_endian, fmt_sz]), data)[0]

def roundup(num, base):
    num,base = int(num),int(base)
    return (num + base - 1) // base * base

class StorageSize(object):
    UNITS = [ "B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB" ]
    KILOBYTE = 1024
    
    @classmethod
    def convert_size(cls, size_in_bytes, target_unit):
        '''Convert size to the target unit'''
        try:
            unit_index = cls.UNITS.index(target_unit.upper())
        except ValueError:
            raise ValueError("Unsupported unint: %s" % target_unit)
        return size_in_bytes / (cls.KILOBYTE ** unit_index)
    
    def __init__(self, size_in_bytes):
        self.size_in_bytes = size_in_bytes
    
    def to(self, target_unit):
        '''Convert the size to the specified unint.'''
        return self.convert_size(target_unit)
    
    def __str__(self):
        size, unit_index = self.size_in_bytes, 0
        
        while size >= self.KILOBYTE and unit_index < len(self.UNITS) - 1:
            size /= self.KILOBYTE
            unit_index += 1
        
        return ('%.2f' % size).rstrip('0').rstrip('.') + self.UNITS[unit_index]
    
    __repr__ = __str__

class ByteParser(object):
    def __init__(self, buffer, endian='big'):
        self.buffer = memoryview(buffer)
        self.endian = endian
        self.pos = 0
    
    def read_u8(self):
        return self._read_integer(size=1, signed=False)
    
    def read_u16(self):
        return self._read_integer(size=2, signed=False)
    
    def read_u32(self):
        return self._read_integer(size=4, signed=False)
    
    def read_u64(self):
        return self._read_integer(size=8, signed=False)
    
    def read_s8(self):
        return self._read_integer(size=1, signed=True)
    
    def read_s16(self):
        return self._read_integer(size=2, signed=True)
    
    def read_s32(self):
        return self._read_integer(size=4, signed=True)
    
    def read_s64(self):
        return self._read_integer(size=8, signed=True)
    
    decode_str = staticmethod({
        '2' : lambda bin : str(bytearray(bin)),
        '3' : lambda bin : bytearray(bin).decode('utf-8')
    }[sys.version[0]])
    
    def read_str(self, return_encode_size=False):
        sz = self.read_u32()
        val = self.decode_str(self.pop(sz))
        
        pad = roundup(sz,4) - sz
        self.skip(pad)
        
        if return_encode_size:
            return [val, 4+sz+pad]
        else:
            return val
    
    def _read_integer(self, size, signed):
        return int_from_bytes(self.pop(size), endian=self.endian, signed=signed)
    
    def pop(self, size):
        data = self.buffer[self.pos : self.pos + size]
        self.pos += size
        assert(len(data) == size)
        return data
    
    def skip(self, size):
        self.pos += size
        assert(self.pos <= len(self.buffer))
