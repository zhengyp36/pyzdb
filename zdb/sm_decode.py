# -*- coding:utf-8 -*-

import sys
from .utils import *
from .dmu import *
from .core import BTree

class SpaceMapManager(object):
    def __init__(self, spa):
        self.spa = spa
        
        # MetaSlabSpaceMap
        self.ms_sm = {}
        for child in self.spa.config['vdev_tree']['children']:
            self.parse_top_vdev(child)
        
        # LogSpacemap
        self.log_sm = {}
        self.parse_log_sm()
    
    def ls(self):
        print('-' * 40)
        print('LogSpacemap:')
        print('-' * 40)
        for txg in self.log_sm:
            print('txg[%d]: sm_obj=%d' % (txg, self.log_sm[txg]))
        print('-' * 40)
        
        print('MetaSlabSpaceMap:')
        print('-' * 40)
        for id in self.ms_sm:
            print('TopVdev[%d]:' % id)
            print('-' * 40)
            print(str(self.ms_sm[id]['table']))
    
    def parse_log_sm(self):
        smzap_obj = self.spa.rdir.lookup(
            'com.delphix:log_spacemap_zap', fmt='num')[0]
        smzap = self.spa.mos.get(smzap_obj, type=Zap)
        
        keys = []
        smzap.ls(keys=keys)
        for key in keys:
            self.log_sm[int(key,base=16)] = smzap.lookup(key, fmt='num')[0]
    
    def parse_top_vdev(self, child):
        dn_msarr = self.spa.mos.get(child['metaslab_array'])
        ms_cnt = child['asize'] >> child['metaslab_shift']
        self.ms_sm[child['id']] = {
            'id'    : child['id'],
            'table' : Int.from_bytes_to_list(
                          dn_msarr.read(0, ms_cnt*8),
                          int_size=8
                      ),
        }
    
    def open_sm(self, obj):
        sm = self.spa.mos.get(obj, type=SpaceMap)
        return {
            'obj'     : obj,
            'sm'      : sm,
            'decoder' : SpaceMapDecoder(Int.from_bytes_to_list(
                            sm.read(0, sm.phys.smp_length),
                            int_size = 8
                        )),
        }

class Dict(dict):
    def __getitem__(self, key):
        if key not in self:
            self[key] = type(self)()
        return super(type(self),self).__getitem__(key)

class SpaceMapDecoder(object):
    def __init__(self, data):
        self.data = data
        self.reset()
    
    def reset(self, pos=0):
        self.pos = pos
    
    def dumpTrees(self, trees):
        pass
    
    def dumpTree(self, tree):
        pass
    
    def makeTrees(self):
        self.reset()
        
        trees = Dict()
        while self.fill_next_bump(trees):
            pass
        return trees
    
    def get_tree(self, trees=None, intro=None, vdev_id=None):
        def cmp_range(x,y):
            assert(x['run_len'] > 0 and y['run_len'] > 0)
            
            r1 = [x['offset'], x['offset'] + x['run_len']]
            r2 = [y['offset'], y['offset'] + y['run_len']]
            
            if r1[1] <= r2[0] or r2[1] <= r1[0]:
                return int(r2[1] <= r1[0]) - int(r1[1] <= r2[0])
            elif r1 == r2:
                return 0
            else:
                raise Exception(
                    'cmp_range error: x={%s},y={%s}' % (str(x),str(y)))
        
        if not trees and not intro and not vdev_id:
            return BTree(dict, cmp_range)
        
        T = trees[intro['txg']][intro['syncpass']][intro['maptype']]
        if vdev_id not in T:
            T[vdev_id] = BTree(type(intro), cmp_range)
        return T[vdev_id]
    
    def fill_tree(self, tree, sm):
        def copy(sm):
            return {k:sm[k] for k in sm}
        
        def merge(prev, next):
            assert(prev['vdev_id'] == next['vdev_id'])
            assert(prev['maptype'] == next['maptype'])
            
            prev_end,next_start = prev['offset']+prev['run_len'],next['offset']
            if prev_end < next_start:
                return None
            
            assert(prev_end == next_start)
            new = {k:prev[k] for k in prev}
            new['offset'] = prev['offset']
            new['run_len'] = prev['run_len'] + next['run_len']
            
            if 'merge' in prev:
                new['merge'] = prev['merge'] + 1
                assert('merge' not in next)
            elif 'merge' in next:
                new['merge'] = next['merge'] + 1
                assert('merge' not in prev)
            else:
                new['merge'] = 1
            
            return new
        
        insert = copy(sm)
        while True:
            exist,where = tree.find(insert, True)
            if exist is not None:
                raise Exception('repeat range exist<%s> vs new<%s>' % (
                    str(exist), str(insert)))
            
            if where is not None:
                prev = tree.prev(where.copy())
                if prev is not None:
                    new = merge(prev, insert)
                    if new is not None:
                        tree.remove(prev)
                        insert = new
                        continue
                
                next = tree.next(where.copy())
                if next is not None:
                    new = merge(insert, next)
                    if new is not None:
                        tree.remove(next)
                        insert = new
                        continue
                
                tree.add(insert, where)
                break
            else:
                tree.add(insert)
                break
    
    def fill_next_bump(self, trees):
        intro,sms = self.next_bump()
        if not intro and not sms:
            return False
        
        for sm in sms:
            sm['intro'] = intro
            self.fill_tree(self.get_tree(trees, intro, sm['vdev_id']), sm)
        
        return True
    
    def dump_all(self, out=sys.stdout):
        while self.dump_next_bump(out=out):
            pass
    
    def dump_next_bump(self, out=sys.stdout):
        intro,sms = self.next_bump()
        
        if not intro and not sms:
            out.write('Traverse done\n')
        else:
            assert(intro and sms)
            print('=' * 40)
            for entry in [intro] + sms:
                print('-' * 40)
                self._dump(entry, out=out)
            ret = True
        
        out.flush()
        return ret
    
    def next_txg_bump(self, dump=False, out=sys.stdout):
        sms_array = []
        
        while True:
            orig_pos = self.pos
            intro,sms = self.next_bump()
            if intro and sms:
                if sms_array:
                    if intro['txg'] != sms_array[0]['txg']:
                        self.pos = orig_pos
                        break
                sms_array += [intro] + sms
            else:
                break
        
        if dump:
            self.dump_sm_array(sms_array, out=out)
        else:
            return sms_array
    
    @classmethod
    def dump_sm_array(cls, sms_array, out=sys.stdout):
        widths = cls.dump_width(sms_array)
        for sm in sms_array:
            cls.dump_sm(sm, out=out, widths=widths)
    
    @classmethod
    def dump_sm(cls, sm, out=sys.stdout, widths=None):
        if widths:
            startLen,endLen,lenLen = widths
        else:
            startLen,endLen,lenLen = [1]*3
        
        maptype = {
            0 : 'ALLOC',
            1 : 'FREE ',
        }
        
        if sm['type'] == 'Intro':
            out.write('INTRO: txg=%d, pass=%d, type=<%-5s>\n' % (
                sm['txg'], sm['syncpass'], maptype[sm['maptype']]
            ))
        else:
            vd = ''
            if sm['vdev_id'] is not None:
                vd = 'vdev=<%d>, ' % sm['vdev_id']
            
            out.write('%-5s: %srange=[%*d,%*d), length=%*d, vdev=%s\n' % (
                maptype[sm['maptype']], vd,
                startLen, sm['offset'],
                endLen, sm['offset'] + sm['run_len'],
                lenLen, sm['run_len'],
                str(sm['vdev_id'])
            ))
    
    @classmethod
    def dump_width(cls, sms_array):
        try:
            maxValue = (
                max([
                    sm['offset'] for sm in sms if 'offset' in sm
                ]),
                max([
                    sm['offset']+sm['run_len'] for sm in sms if 'offset' in sm
                ]),
                max([
                    sm['run_len'] for sm in sms if 'run_len' in sm
                ]),
            )
            return [len('%d'%i) for i in maxValue]
        except:
            return [1]*3
    
    def next_bump(self, dump=False, out=sys.stdout):
        intro,sms = {},[]
        while True:
            orig_pos = self.pos
            entry = self._next()
            if entry is None:
                break
            elif entry['type'] == 'Intro':
                if intro:
                    self.pos = orig_pos
                    break
                else:
                    intro = entry
            else:
                assert(intro and entry['type'] in ['SM1','SM2'])
                sms.append(entry)
        
        assert((not not intro) == (not not sms))
        if dump:
            for sm in [intro] + sms:
                out.write(str(sm) + '\n')
            out.flush()
        else:
            return intro,sms
    
    def _next(self):
        if self.pos == len(self.data):
            return None
        
        val = Int(self.data[self.pos])
        if val.bit_field(63,1) == 0:
            self.pos += 1
            return self._SM1(val)
        elif val.bit_field(62,2) == 3:
            self.pos += 2
            assert(self.pos <= len(self.data))
            return self._SM2([val] + [Int(self.data[self.pos-1])])
        elif val.bit_field(62,2) == 2:
            self.pos += 1
            if val.bit_field(0,62) == 0:
                return self._next()
            else:
                return self._Intro(val)
        else:
            raise Exception(
                "Invalid space map data '0x%x'" % self.data[self.pos])
    
    def _Intro(self, val):
        assert(val.bit_field(60,2) in [0,1])
        return {
            'type'    : 'Intro',
            'txg'     : val.bit_field( 0, 50),
            'syncpass': val.bit_field(50, 10),
            'maptype' : val.bit_field(60,  2),
        }
    
    def _SM1(self, val):
        assert(val.bit_field(63,1) == 0)
        return {
            'type'    : 'SM1',
            'vdev_id' : None,
            'maptype' : val.bit_field(15,  1),
            'offset'  : val.bit_field(16, 47),
            'run_len' : val.bit_field( 0, 15) + 1,
        }
    
    def _SM2(self, val):
        assert(val[0].bit_field(60,2) == 0)
        return {
            'type'    : 'SM2',
            'vdev_id' : val[0].bit_field( 0, 24),
            'maptype' : val[1].bit_field(63,  1),
            'offset'  : val[1].bit_field( 0, 63),
            'run_len' : val[0].bit_field(24, 36) + 1,
        }
    
    def _dump(self, info, out=sys.stdout):
        entries = [ 
            [ 'txg',      lambda v:('%d'%v)                ],
            [ 'syncpass', lambda v:('%d'%v)                ],
            [ 'vdev_id',  lambda v:('%d'%v)                ],
            [ 'maptype',  lambda v:{0:'alloc',1:'free'}[v] ],
            [ 'offset',   lambda v:('%d'%v)                ],
            [ 'run_len',  lambda v:('%d'%v)                ],
        ]
        keylen = max([len(ent[0]) for ent in entries])
        for ent in entries:
            if ent[0] in info and info[ent[0]] is not None:
                out.write('%-*s : %s\n' % (keylen, ent[0], ent[1](info[ent[0]])))
        out.flush()
