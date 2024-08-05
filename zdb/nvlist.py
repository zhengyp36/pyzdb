# -*- coding:utf-8 -*-

from . import utils

class NVListDataType(object):
    def __init__(self, data_type):
        self.data_type = data_type
    
    def __str__(self):
        return self.value2name(self.data_type)
    
    __repr__ = __str__
    
    @classmethod
    def initDataTypeDict(cls):
        if not cls.NAME_TO_VALUE or not cls.VALUE_TO_NAME:
            value = cls.MIN_VALUE
            for name in cls.DataTypeList:
                cls.NAME_TO_VALUE[name] = value
                cls.VALUE_TO_NAME[value] = name
                value += 1
            cls.MAX_VALUE = value
    
    @classmethod
    def name2value(cls, name):
        cls.initDataTypeDict()
        if name in cls.NAME_TO_VALUE:
            return cls.NAME_TO_VALUE[name]
        else:
            return cls.MIN_VALUE - 1
    
    @classmethod
    def value2name(cls, value):
        cls.initDataTypeDict()
        if value in cls.VALUE_TO_NAME:
            return cls.VALUE_TO_NAME[value]
        else:
            return '{%d?[%d~%d]}' % (value, cls.MIN_VALUE, cls.MAX_VALUE)
    
    NAME_TO_VALUE,VALUE_TO_NAME = {},{}
    MIN_VALUE = MAX_VALUE = -1
    
    DataTypeList = [
        'DATA_TYPE_DONTCARE',    # -1
        'DATA_TYPE_UNKNOWN',     # 0
        'DATA_TYPE_BOOLEAN',
        'DATA_TYPE_BYTE',
        'DATA_TYPE_INT16',
        'DATA_TYPE_UINT16',
        'DATA_TYPE_INT32',
        'DATA_TYPE_UINT32',
        'DATA_TYPE_INT64',
        'DATA_TYPE_UINT64',
        'DATA_TYPE_STRING',
        'DATA_TYPE_BYTE_ARRAY',
        'DATA_TYPE_INT16_ARRAY',
        'DATA_TYPE_UINT16_ARRAY',
        'DATA_TYPE_INT32_ARRAY',
        'DATA_TYPE_UINT32_ARRAY',
        'DATA_TYPE_INT64_ARRAY',
        'DATA_TYPE_UINT64_ARRAY',
        'DATA_TYPE_STRING_ARRAY',
        'DATA_TYPE_HRTIME',
        'DATA_TYPE_NVLIST',
        'DATA_TYPE_NVLIST_ARRAY',
        'DATA_TYPE_BOOLEAN_VALUE',
        'DATA_TYPE_INT8',
        'DATA_TYPE_UINT8',
        'DATA_TYPE_BOOLEAN_ARRAY',
        'DATA_TYPE_INT8_ARRAY',
        'DATA_TYPE_UINT8_ARRAY',
    ]

class NVListParser(utils.ByteParser):
    DEBUG = True
    
    def __init__(self, buffer, endian='big', formatter=None):
        super(type(self), self).__init__(buffer, endian=endian)
        if formatter is not None:
            self.formatter = formatter
    
    def parse(self, nvlistType):
        instance = nvlistType()
        instance.nvheader = self.read_nvheader()
        self.read_nvlist(instance=instance)
        return instance
    
    NVHEADER_ITEMS = ['encoding', 'host-endian', 'reserved']
    def read_nvheader(self):
        return {
            'encoding'   :  {
                                0:'NV_ENCODE_NATIVE',
                                1:'NV_ENCODE_XDR',
                            }[self.read_u8()],
            'host-endian':  {
                                0:'big',
                                1:'little',
                            }[self.read_u8()],
            'reserved'   :  [
                                self.read_u8(),
                                self.read_u8()
                            ]
        }
    
    def read_nvlist(self, instance=None, parent=None):
        if instance is None:
            assert(parent)
            instance = type(parent)(parent=parent)
        
        instance.nvattr = self.read_nvattr()
        while True:
            nvp = self.read_nvpair(nvl=instance)
            if nvp is None:
                break
            else:
                instance.add(nvp)
        
        return instance
    
    NVATTR_ITEMS = ['version', 'nvflag']
    def read_nvattr(self):
        return {
            'version' : self.read_s32(),
            'nvflag'  : self.nvflagstr(self.read_s32())
        }
    
    def read_nvpair(self, nvl):
        sz,nvp,orig_pos = 0,{},self.pos
        
        nvp['encode_size'] = self.read_s32()
        sz += 4
        
        nvp['decode_size'] = self.read_s32()
        sz += 4
        
        if nvp['encode_size'] == 0 or nvp['decode_size'] == 0:
            assert(nvp['encode_size'] == 0 and nvp['decode_size'] == 0)
            return None
        
        nvp['name'],_sz = self.read_str(return_encode_size=True)
        sz += _sz
        
        nvp['data_type'] = NVListDataType(self.read_s32())
        sz += 4
        
        nvp['nelem'] = self.read_s32()
        sz += 4
        
        nvp['value'],_sz = self.read_nvpair_value(
            nvp, nvp['encode_size']-sz, nvl)
        sz += _sz
        
        assert(orig_pos + sz == self.pos)
        
        nvp['formatter'] = self.formatter(nvp['name'])
        return nvp
    
    def read_nvpair_value(self, nvp, value_size, nvl):
        orig_pos = self.pos
        
        dt = str(nvp['data_type'])
        ops = {
            'DATA_TYPE_UINT64'        : self.read_u64,
            'DATA_TYPE_STRING'        : self.read_str,
            'DATA_TYPE_BOOLEAN'       : self.read_boolean,
            'DATA_TYPE_BOOLEAN_VALUE' : self.read_boolean_value,
        }
        
        if dt in ops:
            value = ops[dt]()
        elif dt == 'DATA_TYPE_NVLIST':
            value = self.read_nvlist(parent=nvl)
        elif dt == 'DATA_TYPE_NVLIST_ARRAY':
            assert(nvp['nelem'] >= 1)
            value,nelem = [],nvp['nelem']
            while nelem > 0:
                value.append(self.read_nvlist(parent=nvl))
                nelem -= 1
            assert(len(value) == nvp['nelem'])
        else:
            value = None
            self.skip(value_size)
            if not self.DEBUG:
                raise ValueError("NVList data type '%s' not supported" % dt)
        
        assert(self.pos - orig_pos == value_size)
        return [value,value_size]
    
    def read_boolean(self):
        return ''
    
    def read_boolean_value(self):
        value_table = {0:False, 1:True}
        value = self.read_s32()
        assert(value in value_table)
        return value_table[value]
    
    @classmethod
    def formatter(cls, name):
        if 'guid' in name:
            return hex
        else:
            return str
    
    @classmethod
    def nvflagstr(cls, flag):
        NV_FLAGS = [
            ['NV_UNIQUE_NAME.0x1',      0x1],
            ['NV_UNIQUE_NAME_TYPE.0x2', 0x2],
        ]
        
        names = []
        for item in NV_FLAGS:
            if flag & item[1]:
                names.append(item[0])
                flag &= ~item[1]
        
        if flag != 0:
            names.append('?.'+hex(flag))
        
        return '|'.join(names)

class NVList(object):
    def __init__(self, parent=None):
        self.parent = parent
        self.nvheader = {}
        self.nvattr = {}
        self.elems = {}
        self.elem_order = []
    
    def keys(self):
        return [ k for k in self.elem_order ]
    
    def __contains__(self, key):
        return key in self.elems
    
    def __getitem__(self, key):
        if key not in self.elems:
            raise KeyError("'%s' not found in the nvlist" % key)
        return self.elems[key]['value']
    
    def add(self, nvpair):
        assert(nvpair['name'] not in self.elems)
        self.elems[nvpair['name']] = nvpair
        self.elem_order.append(nvpair['name'])
    
    @classmethod
    def parse(cls, buffer, endian='big'):
        return NVListParser(buffer, endian=endian).parse(cls)
    
    def dump(self, indent=0, info=None):
        maxlen = lambda d,m=0 : max([len(k) for k in d]+[m])
        keylen = maxlen(self.nvheader, m=0)
        keylen = maxlen(self.nvattr, m=keylen)
        keylen = maxlen(self.elem_order, m=keylen)
        
        tab = 2 * ' '
        line = '-' * (80 - indent * len(tab))
        enterLine = '<' * (80 - indent * len(tab))
        exitLine = '>' * (80 - indent * len(tab))
        
        if info is None:
            info = []
        append = lambda msg : info.append(indent * tab + msg)
        
        if self.nvheader:
            append(line)
            for k in NVListParser.NVHEADER_ITEMS:
                append('%-*s : %s' % (keylen, k, str(self.nvheader[k])))
        
        append(line)
        for k in NVListParser.NVATTR_ITEMS:
            append('%-*s : %s' % (keylen, k, str(self.nvattr[k])))
        
        nvpair2str = lambda nvp : '%s|%d.%d|%d{%s}' % (
            str(nvp['data_type']),
            nvp['encode_size'], nvp['decode_size'], nvp['nelem'],
            nvp['formatter'](nvp['value'])
        )
        
        append(line)
        for k in self.elem_order:
            nvp = self.elems[k]
            append('%-*s : %s' % (keylen, k, nvpair2str(nvp)))
            
            dt = str(nvp['data_type'])
            if dt == 'DATA_TYPE_NVLIST':
                nvlarr = [nvp['value']]
            elif dt == 'DATA_TYPE_NVLIST_ARRAY':
                nvlarr = nvp['value']
            else:
                continue
            
            append(enterLine)
            for nvl in nvlarr:
                nvl.dump(indent=indent+1, info=info)
            append(exitLine)
        append(line)
        
        if indent == 0:
            print('\n'.join(info))
