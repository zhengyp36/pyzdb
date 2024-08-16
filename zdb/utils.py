# -*- coding:utf-8 -*-

import sys
import struct
import inspect

def Error(ErrorType):
    class ErrorImpl(Exception):
        def __init__(self, source, value=None):
            super(type(self),self).__init__(ErrorType.__name__)
            self.source = source
            self.value = value
        
        def __str__(self):
            s = '%s from %s(%s)' % (
                str(self.args[0]),
                str(type(self.source)),
                str(self.source)
            )
            if self.value is not None:
                s += ', value={%s}' % str(self.value)
            return s
    
    return ErrorImpl

@Error
class MagicError(object):
    pass

@Error
class HoleError(object):
    pass

@Error
class Unsupported(object):
    pass

def EnumType(TypeDef):
    class TypeImplement(TypeDef):
        def __init__(self, entry, enum_value):
            def getargspec(method):
                if sys.version[0] == '2':
                    try:
                        return inspect.getargspec(method).args
                    except TypeError:
                        return []
                elif sys.version[0] == '3':
                    return ([ 'self' ] + [ str(s) for s in
                        inspect.signature(method).parameters.values()
                        if str(s) not in ['*args','**kwargs']
                    ])
                else:
                    raise Exception(
                        'Unsupported Python version {%s}' % sys.version)
            
            args = getargspec(super(type(self),self).__init__)
            if len(args) == 0: # __init__ not implemented
                pass
            elif len(args) == 1: # __init__(self)
                super(type(self),self).__init__()
            elif len(args) == 2: # __init__(self,entry)
                super(type(self),self).__init__(entry)
            elif len(args) == 3: # __init__(self,entry,enum_value)
                super(type(self),self).__init__(entry, enum_value)
            else: # __init__(??)
                super(type(self),self).__init__(entry, enum_value)
            
            self._name      = entry[0]
            self._enum_name = entry[1]
            self._value     = enum_value
        
        def __str__(self):
            return self._name
        
        def __repr__(self):
            return self._enum_name
        
        def __int__(self):
            return self._value
        
        def has(self, flag):
            return not not (self._value & flag)
        
        @classmethod
        def from_str(cls, name):
            return cls.MEMBERS_DICT[str(name)]
        
        @classmethod
        def from_int(cls, value):
            return cls.MEMBERS_DICT[int(value)]
        
        @classmethod
        def ls_range(cls):
            values = list(set([i._value for i in cls.MEMBERS_LIST]))
            values.sort()
            
            start = last = values[0]
            for curr in values[1:]:
                if last + 1 < curr:
                    print('%d -> %d' % (start, last))
                    start = last = curr
                else:
                    last = curr
            print('%d -> %d' % (start, last))
        
        @classmethod
        def ls(cls, sort=False):
            if sort:
                members = cls.MEMBERS_LIST[:]
                members.sort(key=lambda m : m._value)
            else:
                members = cls.MEMBERS_LIST
            
            l1 = max([len(i._name) for i in members])
            l2 = max([len(i._enum_name) for i in members])
            for inst in members:
                print('%-*s : %-*s : %d' % (
                    l1, inst._name, l2, inst._enum_name, inst._value
                ))
        
        __doc__ = TypeDef.__doc__
        MEMBERS_DICT,MEMBERS_LIST = {},[]
    
    v = -1
    for entry in TypeDef.TABLE:
        n,e,_v = entry[:3]
        if _v is not None:
            v = _v
        else:
            v += 1
        
        inst = TypeImplement(entry, v)
        
        TypeImplement.MEMBERS_LIST.append(inst)
        TypeImplement.MEMBERS_DICT[n] = inst
        TypeImplement.MEMBERS_DICT[e] = inst
        TypeImplement.MEMBERS_DICT[v] = inst
        
        setattr(TypeImplement, n, inst)
        setattr(TypeImplement, e, inst)
    
    return TypeImplement

@EnumType
class Endian(object):
    TABLE = [
        [ 'big',    'BIG',    0 ],
        [ 'little', 'LITTLE', 1 ],
    ]
    
    @classmethod
    def set_default(cls, endian):
        assert(isinstance(endian, cls))
        setattr(cls, 'default', endian)
Endian.set_default(Endian.little)

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
    def from_bytes(cls, bytes, endian=Endian.default, signed=False):
        fmt_e = cls.FORMAT_ENDIAN[endian]
        fmt_sz = cls.FORMAT_SIZE[signed][len(bytes)]
        return struct.unpack(fmt_e+fmt_sz, bytes)[0]
    
    @classmethod
    def from_bytes_to_list(cls,
        bytes, int_size, endian=Endian.default, signed=False):
        
        count = len(bytes) // int_size
        fmt_e = cls.FORMAT_ENDIAN[endian]
        fmt_sz = cls.FORMAT_SIZE[signed][int_size] * count
        return list(struct.unpack(fmt_e+fmt_sz, bytes))
    
    def __init__(self, value=0):
        self._value = int(value)
    
    def roundup(self, base):
        return (self._value + base - 1) // base * base
    
    def bit_field(self, start, length):
        return (self._value >> start) & ((1 << length) - 1)
    
    def highbit(self):
        s = (bin(self._value)[2:].strip('L')+'L').strip('0')[:-1]
        return len(s)

class Str(object):
    @classmethod
    def encode(cls, s):
        return {
            '2' : lambda s : bytearray(s),
            '3' : lambda s : bytearray(s.encode('utf-8')),
        }[sys.version[0]](s)
    
    @classmethod
    def decode(cls, bytes):
        return {
            '2' : lambda bin : str(bytearray(bin)),
            '3' : lambda bin : bytearray(bin).decode('utf-8'),
        }[sys.version[0]](bytes).strip('\x00')

class Crc64Poly(object):
    @classmethod
    def hash(cls, key, salt):
        cls._init_table()
        assert(isinstance(key,str))
        h = salt
        for i in Str.encode(key):
            h = (h >> 8) ^ cls._table[(h^i)&0xFF]
        return h
    
    @classmethod
    def _init_table(cls):
        if cls._table is None:
            ZFS_CRC64_POLY = 0xC96C5795D7870F42
            def gen(n):
                for i in range(8):
                    n = (n >> 1) ^ (-(n&1) & ZFS_CRC64_POLY)
                return n
            cls._table = [gen(i) for i in range(256)]
            assert(cls._table[128] == ZFS_CRC64_POLY)
    _table = None

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
        val = Str.decode(self.pop(sz))
        
        pad = Int(sz).roundup(4) - sz
        self.skip(pad)
        
        if not return_encode_size:
            return val
        else:
            return [val, 4+sz+pad]

class CStruct(object):
    repr_detail = True
    
    '''FIELDS is defined by derived class.
    1. An example for blkptr_t:
       --------------------------------------------------
       FIELDS = [
           [ 'blk_dva',       48, DVA,         'str' ],
           [ 'blk_prop',       8, 'u64',       'str' ],
           [ 'blk_pad',       16, 'u64.array', 'str' ],
           [ 'blk_phys_birth', 8, 'u64',       'str' ],
           [ 'blk_birth',      8, 'u64',       'str' ],
           [ 'blk_fill',       8, 'u64',       'str' ],
           [ 'blk_cksum',     32, ZioCkSum,    'str' ],
       ]
       --------------------------------------------------
    2. Titles for every row are name, size, converter and formatter,
       where the proto-type of converter is converter(bytes,endian) and
       of formatter is formatter(val) where 'val' is CStruct().fields[name]
    
    Lookup zctypes.py for more details.
    '''
    STRUCT_NAME = ''
    FIELDS = []
    
    conv_skip = lambda bytes, endian : None
    conv_byte = lambda bytes, endian : bytearray(bytes)
    conv_str  = lambda bytes, endian : Str.decode(bytes)
    
    conv_unsigned = lambda bytes, endian : (
        Int.from_bytes(bytes, endian=endian,signed=False)
    )
    conv_array_u8 = lambda bytes, endian : (
        Int.from_bytes_to_list(bytes, int_size=1, endian=endian, signed=False)
    )
    conv_array_u64 = lambda bytes, endian : (
        Int.from_bytes_to_list(bytes, int_size=8, endian=endian, signed=False)
    )
    
    CONVERT_TABLE = {
        '.'         : conv_skip,
        'SKIP'      : conv_skip,
        'byte'      : conv_byte,
        'str'       : conv_str,
        'u8'        : conv_unsigned,
        'u16'       : conv_unsigned,
        'u32'       : conv_unsigned,
        'u64'       : conv_unsigned,
        'u8.array'  : conv_array_u8,
        'u64.array' : conv_array_u64,
    }
    
    FORMAT_TABLE = {
        'str'     : lambda val,inst : str(val),
        'hex'     : lambda val,inst : hex(val).strip('L'),
        'magic32' : lambda val,inst : '0x' + hex(val).strip('L')[2:].zfill(8),
        'magic64' : lambda val,inst : '0x' + hex(val).strip('L')[2:].zfill(16),
    }
    
    @classmethod
    def convert_method(cls, count=1, verify=False):
        def convert(bytes, endian=Endian.default):
            sz = cls.sizeof()
            if verify:
                assert(sz * count == len(bytes))
            return [cls(bytes[i*sz:i*sz+sz]) for i in range(count)]
        return convert
    
    def __init__(self, bytes, endian=Endian.default):
        assert(len(bytes) >= self.sizeof())
        self.fields = {}
        self._endian = endian
        self._do_init(memoryview(bytes))
    
    def _do_init(self, bytes):
        self.set_fields(bytes)
    
    def set_fields(self, bytes, pos=0, field_def=None, field_out=None):
        field_out = self._get_value(field_out, self.fields)
        
        mv = memoryview(bytes)
        for entry in self._get_value(field_def, self.FIELDS):
            name,sz,conv = entry[:3]
            if name != '.':
                if conv in self.CONVERT_TABLE:
                    conv = self.CONVERT_TABLE[conv]
                val = conv(mv[pos:pos+sz],self._endian)
                
                assert(name not in field_out)
                field_out[name] = val
                setattr(self, name, val)
            pos += sz
        
        return pos
    
    def do_format(self, field_def=None, checker=None, keylen=None):
        field_def = self._get_value(field_def, self.FIELDS)
        if keylen is None:
            keylen = max([ len(f[0]) for f in field_def ])
        output = []
        
        output.append(self.STRUCT_NAME + ' {')
        for f in field_def:
            name,sz,_,_fmt = f
            if name != '.':
                if not checker or checker(f):
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
    
    @property
    def endian(self):
        return self._endian
    
    @classmethod
    def indexof(cls, field, field_def=None, verify=False):
        idx = 0
        for entry in cls._get_value(field_def, cls.FIELDS):
            if entry[0] == field:
                return idx
            idx += 1
        
        if verify:
            raise Exception("Field name '%s' not found" % field)
        return -1
    
    @classmethod
    def offsetof(cls, field, field_def=None, verify=False):
        field_def = cls._get_value(field_def, cls.FIELDS)
        idx = cls.indexof(field, field_def=field_def, verify=verify)
        if idx >= 0:
            field_def = field_def[:idx]
        return cls.sizeof(field_def=field_def)
    
    @classmethod
    def sizeof(cls, field_def=None):
        return sum([f[1] for f in cls._get_value(field_def, cls.FIELDS)])
    
    @classmethod
    def _get_value(cls, value, default_value):
        if value is not None:
            return value
        else:
            return default_value
    
    def __str__(self):
        return self.do_format()
    
    def __repr__(self):
        if self.repr_detail:
            return str(self)
        else:
            return object.__repr__(self)

class ZapNameTable(object):
    TABLE = []
    
    @classmethod
    def ls(cls):
        l0 = max([len(str(i[0])) for i in cls.TABLE])
        l1 = max([len(str(i[1])) for i in cls.TABLE])
        for item in cls.TABLE:
            print('%-*s : %-*s' % (l0, str(item[0]), l1, str(item[1])))
