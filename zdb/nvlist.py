# -*- coding:utf-8 -*-

from .utils import *

@EnumType
class NVLDT(object):
    '''NVLDT is nvlist-data-type'''
    TABLE = [
        [ 'dontcare', 'DATA_TYPE_DONTCARE',        -1 ],
        [ 'unknown',  'DATA_TYPE_UNKNOWN',          0 ],
        [ 'bool',     'DATA_TYPE_BOOLEAN',       None ],
        [ 'byte',     'DATA_TYPE_BYTE',          None ],
        [ 's16',      'DATA_TYPE_INT16',         None ],
        [ 'u16',      'DATA_TYPE_UINT16',        None ],
        [ 's32',      'DATA_TYPE_INT32',         None ],
        [ 'u32',      'DATA_TYPE_UINT32',        None ],
        [ 's64',      'DATA_TYPE_INT64',         None ],
        [ 'u64',      'DATA_TYPE_UINT64',        None ],
        [ 'str',      'DATA_TYPE_STRING',        None ],
        [ 'byteA',    'DATA_TYPE_BYTE_ARRAY',    None ],
        [ 's16A',     'DATA_TYPE_INT16_ARRAY',   None ],
        [ 'u16A',     'DATA_TYPE_UINT16_ARRAY',  None ],
        [ 's32A',     'DATA_TYPE_INT32_ARRAY',   None ],
        [ 'u32A',     'DATA_TYPE_UINT32_ARRAY',  None ],
        [ 's64A',     'DATA_TYPE_INT64_ARRAY',   None ],
        [ 'u64A',     'DATA_TYPE_UINT64_ARRAY',  None ],
        [ 'strA',     'DATA_TYPE_STRING_ARRAY',  None ],
        [ 'hrtime',   'DATA_TYPE_HRTIME',        None ],
        [ 'nvlist',   'DATA_TYPE_NVLIST',        None ],
        [ 'nvlistA',  'DATA_TYPE_NVLIST_ARRAY',  None ],
        [ 'boolV',    'DATA_TYPE_BOOLEAN_VALUE', None ],
        [ 's8',       'DATA_TYPE_INT8',          None ],
        [ 'u8',       'DATA_TYPE_UINT8',         None ],
        [ 'boolA',    'DATA_TYPE_BOOLEAN_ARRAY', None ],
        [ 's8A',      'DATA_TYPE_INT8_ARRAY',    None ],
        [ 'u8A',      'DATA_TYPE_UINT8_ARRAY',   None ],
    ]

class NVList(object):
    NV_HEADER = [ 'encoding', 'host-endian', 'reserved' ]
    NV_ATTR   = [ 'version',  'nvflag' ]
    NV_PAIR   = [
        'encode_size', 'decode_size',
        'name', 'data_type', 'nelem', 'value', 'formatter'
    ]
    
    @classmethod
    def from_bytes(cls, bytes):
        inst,xdr = cls(),XDR(bytes)
        
        inst._set_nvheader(xdr)
        cls._parse_nvlist(xdr, inst=inst)
        inst.encode_size = xdr.pos
        
        return inst
    
    def __init__(self, parent=None):
        self.parent      = parent
        
        self.nvheader    = self._init_dict(self.NV_HEADER)
        self.nvattr      = self._init_dict(self.NV_ATTR)
        
        self._items      = {}
        self._item_order = []
        
        self.pos_start   = 0
        self.pos_end     = 0
    
    def __str__(self):
        return '{\n' + self._format(indent=1, tab=2*' ') + '\n}'
    __repr__ = __str__
    
    def __bool__(self):
        return not not self._items
    __nonzero__ = __bool__
    
    def __contains__(self, key):
        return key in self._items
    
    def __getitem__(self, key):
        return self._items[key]['value']
    
    def item(self, key):
        return self._items[key]
    
    @classmethod
    def _parse_nvlist(cls, xdr, inst=None, parent=None):
        if inst is None:
            assert(parent is not None)
            inst = cls(parent=parent)
        
        inst.pos_start = xdr.pos
        inst._set_nvattr(xdr)
        inst._parse_nvpairs(xdr)
        inst.pos_end = xdr.pos
        
        return inst
    
    def _set_nvheader(self, xdr):
        self.nvheader['encoding'   ] = xdr.read_int('s8')
        self.nvheader['host-endian'] = xdr.read_int('s8')
        self.nvheader['reserved'   ] = [xdr.read_int('s8'),xdr.read_int('s8')]
    
    def _set_nvattr(self, xdr):
        self.nvattr['version'] = xdr.read_int('s32')
        self.nvattr['nvflag' ] = xdr.read_int('s32')
    
    def _parse_nvpairs(self, xdr):
        while True:
            nvp = self._next_nvpair(xdr)
            if nvp is not None:
                assert(nvp['name'] not in self._items)
                self._item_order.append(nvp['name'])
                self._items[nvp['name']] = nvp
            else:
                break
    
    def _next_nvpair(self, xdr):
        orig_pos,sz = xdr.pos,0
        nvp = self._init_dict(self.NV_PAIR)
        
        nvp['encode_size'] = xdr.read_int('s32')
        sz += 4
        
        nvp['decode_size'] = xdr.read_int('s32')
        sz += 4
        
        if nvp['encode_size'] == 0 or nvp['decode_size'] == 0:
            assert(nvp['encode_size'] == 0 and nvp['decode_size'] == 0)
            assert(len(self._items) > 0)
            return None
        
        nvp['name'],_sz = xdr.read_str(return_encode_size=True)
        sz += _sz
        
        nvp['data_type'] = NVLDT.from_int(xdr.read_int('s32'))
        sz += 4
        
        nvp['nelem'] = xdr.read_int('s32')
        sz += 4
        
        nvp['value'],_sz = self._parse_nvpair_value(xdr, nvp)
        sz += _sz
        
        assert(orig_pos + sz == xdr.pos)
        nvp['formatter'] = self._get_formatter(nvp)
        
        return nvp
    
    def _parse_nvpair_value(self, xdr, nvp):
        dt  = nvp['data_type']
        if dt in [NVLDT.nvlist, NVLDT.nvlistA]:
            return self._parse_value_nvlist(xdr, nvp)
        else:
            ops = {
                NVLDT.u64   : lambda : (xdr.read_int('u64'),8),
                NVLDT.str   : lambda : xdr.read_str(return_encode_size=True),
                NVLDT.bool  : lambda : ('',0),
                NVLDT.boolV : lambda : (xdr.read_int('s32'),4),
            }
            
            assert(dt in ops)
            val,sz = ops[dt]()
            
            if dt == NVLDT.boolV:
                assert(val in [0,1])
            
            return val,sz
    
    def _parse_value_nvlist(self, xdr, nvp):
        nelem = nvp['nelem']
        assert(nelem >= 1)
        
        pos,arr = xdr.pos,[]
        while nelem > 0:
            arr.append(self._parse_nvlist(xdr, parent=self))
            nelem -= 1
        sz = xdr.pos - pos
        
        if nvp['data_type'] == NVLDT.nvlist:
            assert(len(arr) == 1)
            return arr[0],sz
        else:
            return arr,sz
    
    @classmethod
    def _get_formatter(cls, nvp):
        if 'guid' in nvp['name']:
            return (lambda n : hex(n).strip('L'))
        else:
            return str
    
    def _format(self, indent=0, tab=2*' ', output=None):
        keylen = max([len(n) for n in self._item_order])
        
        if output is None:
            lines = []
        else:
            lines = output
        
        TAB = indent*tab
        append = lambda s : lines.append(TAB+s)
        
        def append_sep(sep,info):
            if info != '':
                info = '[%s]' % str(info)
            half = int((80 - len(TAB) - len(info)) / 2) * sep
            pad = sep * (80 - 2 * len(half) - len(info) - len(TAB))
            append(half + info + half + pad)
        
        enterLine = lambda s='' : append_sep('>',s)
        exitLine  = lambda s='' : append_sep('<',s)
        
        for name in self._item_order:
            item = self._items[name]
            dt,nelem,value = item['data_type'],item['nelem'],item['value']
            
            if dt not in [NVLDT.nvlist, NVLDT.nvlistA]:
                append('%-*s : %s' % (
                    keylen, name,
                    item['formatter'](value)
                ))
            elif dt == NVLDT.nvlist:
                append('%-*s :' % (keylen, name))
                enterLine()
                value._format(indent=indent+1,tab=tab,output=lines)
                exitLine()
            else: # NVLDT.nvlistA
                append('%-*s :' % (keylen, name))
                enterLine(0)
                for i in range(nelem):
                    value[i]._format(indent=indent+1,tab=tab,output=lines)
                    if i != nelem - 1: # not the last nvlist
                        exitLine(i)
                        enterLine(i+1)
                    else: # the last nvlist
                        exitLine(i)
        
        if output is None:
            return '\n'.join(lines)
    
    @classmethod
    def _init_dict(self, keys):
        _dict,default_value = {},None
        for key in keys:
            _dict[key] = default_value
        return _dict
    