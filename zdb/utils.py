# -*- coding:utf-8 -*-

import sys
import struct

class MagicError(Exception):
    def __init__(self, source, value=None):
        super(type(self),self).__init__('MagicError')
        self.source = str(source)
        self.value = value
    
    def __str__(self):
        s = '%s from %s' % (str(self.args[0]), self.source)
        if self.value is not None:
            s += ', value={%s}' % str(self.value)
        return s

class StorageSize(object):
    KILOBYTE = 1024
    UNITS    = [ "B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB" ]
    
    def __init__(self, size):
        self._size = int(size)
    
    @property
    def size(self):
        return self._size
    
    def to(self, unit):
        try:
            idx = self.UNITS.index(unit.upper())
            return float(self._size) / (self.KILOBYTE ** idx)
        except ValueError:
            raise ValueError("Unsupported unit: %s" % unit)
    
    def __str__(self):
        sz,idx = float(self._size),0
        while sz >= self.KILOBYTE and idx < len(self.UNITS) - 1:
            sz /= self.KILOBYTE
            idx += 1
        
        if sz == int(sz):
            return str(int(sz)) + self.UNITS[idx]
        else:
            return ('%.2f' % sz) + self.UNITS[idx]
    
    __repr__ = __str__

class Endian(object):
    @classmethod
    def from_int(cls, value):
        return cls.MEMBERS[int(value)]
    
    @classmethod
    def from_str(cls, name):
        return cls.MEMBERS[name.lower()]
    
    @property
    def value(self):
        return self._value
    
    def __str__(self):
        return self._name
    __repr__ = __str__
    
    @classmethod
    def init_once(cls):
        if not cls.MEMBERS:
            for n,v in [ ['big',0], ['little',1] ]:
                inst = cls()
                setattr(inst, '_name', n)
                setattr(inst, '_value', v)
                cls.MEMBERS[n] = cls.MEMBERS[v] = inst
                setattr(cls, n, inst)
    MEMBERS = {}
Endian.init_once()

class Int(object):
    FORMAT_ENDIAN = {
        Endian.little : '<',
        Endian.big    : '>',
    }
    
    FORMAT_SIZE = {
        False : { 1:'B', 2:'H', 4:'I', 8:'Q' }, # unsigned
        True  : { 1:'b', 2:'h', 4:'i', 8:'q' }, # signed
    }
    
    @classmethod
    def from_bytes(cls, bytes, endian=Endian.little, signed=False):
        fmt_e = cls.FORMAT_ENDIAN[endian]
        fmt_sz = cls.FORMAT_SIZE[signed][len(bytes)]
        return struct.unpack(fmt_e+fmt_sz, bytes)[0]
    
    @classmethod
    def from_bytes_to_list(cls,
        bytes, int_size, endian=Endian.little, signed=False):
        
        count = len(bytes) // int_size
        fmt_e = cls.FORMAT_ENDIAN[endian]
        fmt_sz = cls.FORMAT_SIZE[signed][int_size] * count
        return list(struct.unpack(fmt_e+fmt_sz, bytes))
    
    @classmethod
    def convert_method(cls, int_size):
        def convert(bytes, endian=Endian.little, signed=False):
            return cls.from_bytes_to_list(bytes,
                int_size, endian=endian, signed=signed)
        return convert
    
    def __init__(self, value=0):
        self._value = int(value)
    
    def roundup(self, base):
        return (self._value + base - 1) // base * base
    
    def bit_field(self, start, length):
        return (self._value >> start) & ((1 << length) - 1)

class XDR(object):
    def __init__(self, bytes):
        self.buffer = memoryview(bytes)
        self.endian = Endian.big
        self.pos = 0
    
    def pop(self, size):
        data = self.buffer[self.pos : self.pos + size]
        self.pos += size
        assert(len(data) == size)
        return data
    
    def skip(self, size):
        self.pos += size
        assert(self.pos <= len(self.buffer))
    
    def read_int(self, type):
        signed = {'u':False,'s':True}[type[0].lower()]
        int_sz = int(type[1:]) // 8
        
        return Int.from_bytes(
            bytes  = self.pop(int_sz),
            endian = self.endian,
            signed = signed
        )
    
    def read_str(self, return_encode_size=False):
        sz = self.read_int('u32')
        val = {
            '2' : lambda bin : str(bytearray(bin)),
            '3' : lambda bin : bytearray(bin).decode('utf-8'),
        }[sys.version[0]](self.pop(sz))
        
        pad = Int(sz).roundup(4) - sz
        self.skip(pad)
        
        if not return_encode_size:
            return val
        else:
            return [val, 4+sz+pad]

class CStruct(object):
    '''FIELDS is defined by derived class.
    1. An example for blkptr_t:
       --------------------------------------------------
       FIELDS = [
           [ 'blk_dva',       48, DVA,         str ],
           [ 'blk_prop',       8, 'u64',       str ],
           [ 'blk_pad',       16, 'u64.array', str ],
           [ 'blk_phys_birth', 8, 'u64',       str ],
           [ 'blk_birth',      8, 'u64',       str ],
           [ 'blk_fill',       8, 'u64',       str ],
           [ 'blk_cksum',     32, ZioCkSum,    str ],
       ]
       --------------------------------------------------
    2. Titles for every row are name, size, converter and formatter,
       where the proto-type of converter is converter(bytes,endian) and
       the formatter's formatter(val) where 'val' is CStruct().fields[name]
    
    Lookup cstruct.py for more details.
    '''
    STRUCT_NAME = ''
    FIELDS = []
    
    CONVERT_TABLE = {
        'u64'       : Int.from_bytes,
        'u64.array' : Int.convert_method(int_size=8),
    }
    
    FORMAT_TABLE = {
        'str'     : lambda val,inst : str(val),
        'magic32' : lambda val,inst : '0x' + hex(val)[2:].zfill(8),
    }
    
    def __init__(self, bytes, endian=Endian.little):
        mv = memoryview(bytes)
        self._init_this_type()
        self._set_endian(mv, endian)
        self._init_fields(mv)
        self._validate()
    
    def _set_endian(self, bytes, endian):
        # uberblock and blkptr may redefine the method
        self._endian = endian
    
    def _init_fields(self, mv):
        pos,self.fields = 0,{}
        for name,sz,conv,_ in self.FIELDS:
            if name != '.':
                if conv in self.CONVERT_TABLE:
                    conv = self.CONVERT_TABLE[conv]
                val = conv(mv[pos:pos+sz],self._endian)
                
                assert(name not in self.fields)
                self.fields[name] = val
                setattr(self, name, val)
            pos += sz
    
    def _validate(self):
        # Implemented by derived class
        pass
    
    @classmethod
    def _init_this_type(cls):
        # Implemented by derived class such BlkPtr
        pass
    
    @property
    def endian(self):
        return self._endian
    
    @classmethod
    def count_offset(cls, field, verify=False):
        off = 0
        for name,sz,_,_ in cls.FIELDS:
            if name == field:
                return off
            off += sz
        
        if verify:
            raise Exception("Field name '%s' not found" % field)
        return off
    
    def do_format(self, checker=None, keylen=None):
        if keylen is None:
            keylen = max([ len(f[0]) for f in self.FIELDS ])
        output = []
        
        output.append(self.STRUCT_NAME + ' {')
        for f in self.FIELDS:
            if not checker or checker(f):
                name,_,_,_fmt = f
                if _fmt in self.FORMAT_TABLE:
                    fmt = self.FORMAT_TABLE[_fmt]
                elif isinstance(_fmt,str):
                    fmt = lambda _1,_2 : _fmt
                else:
                    fmt = _fmt
                output.append('  %-*s : %s' % (
                    keylen, name, fmt(self.fields[name],self)
                ))
        output.append('}')
        
        return '\n'.join(output)
    
    def __str__(self):
        return self.do_format()
    
    __repr__ = __str__
