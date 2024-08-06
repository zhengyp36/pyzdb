# -*- coding:utf-8 -*-

import sys
import struct

INTEGER_FORMATTER = {1:'B', 2:'H', 4:'I', 8:'Q'}
INTEGER_SIZES = list(INTEGER_FORMATTER.keys())
INTEGER_SIZES.sort()

def int_to_endian(val):
    return {0:'big',1:'little'}[val]

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

def read_u64(bin, offset=0, count=1, endian='little'):
    bin,pos,r = memoryview(bin),offset,[]
    while count > 0:
        r.append(int_from_bytes(bin[pos:pos+8], endian=endian))
        pos += 8
        count -= 1
    return r

def roundup(num, base):
    num,base = int(num),int(base)
    return (num + base - 1) // base * base

def bitfield_read(value, start, end):
    length = end - start
    mask = (1 << length) - 1
    return (value >> start) & mask

class HexInt(object):
    def __init__(self, value=0):
        self.value = value
    
    def __str__(self):
        return hex(self.value)
    
    __repr__ = __str__

class CStructField(object):
    def __init__(self, name, szInU64, convert, formatter=None):
        self.name = name
        self.szInU64 = szInU64
        self.convert = convert
        
        if isinstance(formatter,str):
            self.formatter = lambda _ : formatter
        elif callable(formatter):
            self.formatter = formatter
        else:
            assert(formatter is None)
            self.formatter = str

class CStruct(object):
    FIELDS,SIZE_U64 = [],0
    
    def __init__(self, bins=None, ints=None, endian='little'):
        self.desc_order = []
        self.desc = {}
    
    def setattr(self, name, value):
        self.desc[name] = value
        setattr(self, name, value)
    
    def setattrs_u64(self, data):
        pos = 0
        for field in self.FIELDS:
            assert(field.name not in self.desc)
            self.desc_order.append(field.name)
            
            self.setattr(
                field.name,
                field.convert(data[ pos : pos+field.szInU64 ])
            )
            
            pos += field.szInU64
    
    def __str__(self):
        output,keylen = [],max([ len(field.name) for field in self.FIELDS ])
        output.append('{')
        for field in self.FIELDS:
            output.append('  %-*s : %s' % (
                keylen, field.name,
                field.formatter(self.desc[field.name])
            ))
        output.append('}')
        return '\n'.join(output)
    
    __repr__ = __str__
    
    def __getitem__(self, key):
        return self.desc[key]
    
    @classmethod
    def count_offset(cls, target_field):
        offset = 0
        for field in self.FIELDS:
            if field.name == target_field:
                return offset
            else:
                offset += field.szInU64
        return None
    
    @classmethod
    def from_bins(cls, bins):
        '''Convert from binary data'''
        return cls(bins=bins)
    
    @classmethod
    def from_ints(cls, ints, endian='little'):
        '''Convert from integer data'''
        return cls(ints=ints, endian=endian)

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
