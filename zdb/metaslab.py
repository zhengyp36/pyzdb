# -*- coding:utf-8 -*-

import sys
from .dmu import *
from .utils import *
from .core import BTree
from .sm_decode import *

class RangeSeg(object):
    def __init__(self, offset, length):
        self.offset = offset
        self.length = length
    
    @property
    def end(self):
        return self.offset + self.length
    
    def __repr__(self):
        return '[%d,%d)' % (self.offset, self.end)
    
    def contains(self, n):
        return n >= self.offset and n < self.end
    
    def contains_other(self, other):
        return self.offset <= other.offset and self.end >= other.end
    
    def intersect(self, other):
        return self.contains(other.offset) or other.contains(self.offset)
    
    def cmp(self, other):
        if self.intersect(other):
            return 0
        else:
            return (self.offset>other.offset) - (other.offset>self.offset)
    
    def merge(self, other):
        r = self.cmp(other)
        assert(r != 0)
        
        if r < 0 and self.end == other.offset:
            return type(self)(self.offset, self.length + other.length)
        elif r > 0 and other.end == self.offset:
            return type(self)(other.offset, self.length + other.length)
        else:
            return None

class RangeTree(object):
    def __init__(self):
        self.reset()
    
    def reset(self):
        self.btree = BTree(RangeSeg, lambda x,y:x.cmp(y))
    
    def free(self, r, initial=False):
        if initial:
            self.btree.clear()
        self._add(element=r)
    
    def alloc(self, r):
        orig_seg = self.btree.find(r)
        assert(orig_seg.contains_other(r))
        self.btree.remove(element=orig_seg)
        
        segs = [
            RangeSeg(orig_seg.offset, r.offset - orig_seg.offset),
            RangeSeg(r.end, orig_seg.end - r.end)
        ]
        for seg in segs:
            if seg.length > 0:
                self._add(element=seg)
    
    def dump(self, out=sys.stdout):
        out.write('UsableRangeSegs:\n')
        for r in self.btree.tolist():
            out.write(repr(r) + '\n')
        out.flush()
    
    def _add(self, element):
        tree = self.btree
        new = element
        
        while True:
            old,where = tree.find(new,return_where=True)
            if old:
                msg = []
                msg.append('Old rangeSeg: %s' % repr(old))
                msg.append('New rangeSeg: %s' % repr(new))
                raise Exception('\n'.join(msg))
            
            if where:
                prev = tree.prev(where, update_where=False)
                if prev:
                    merge = new.merge(prev)
                    if merge:
                        new = merge
                        tree.remove(element=prev)
                        continue
                
                next = tree.next(where, update_where=False)
                if next:
                    merge = new.merge(next)
                    if merge:
                        new = merge
                        tree.remove(element=next)
                        continue
            
            tree.add(new)
            break

class Metaslab(object):
    def __init__(self, spa, tvd_id, ms_id):
        self.spa = spa
        self.replay_table = {}
        self.replayed_txg = 0
        self.rt = RangeTree()
        self._info = {
            'tvd_id' : tvd_id,
            'ms_id'  : ms_id,
        }
        
        nvl = spa.config['vdev_tree']['children'][tvd_id]
        self._info['start' ] = ms_id << nvl['metaslab_shift']
        self._info['length'] = 1 << nvl['metaslab_shift']
        
        msarr = spa.mos.get(nvl['metaslab_array'])
        self._info['smobj' ] = Int.from_bytes(msarr.read(ms_id*8, 8))
        
        smzap_obj = spa.rdir.lookup(
            'com.delphix:log_spacemap_zap',fmt='num')[0]
        smzap = spa.mos.get(smzap_obj, type=Zap)
        
        logsm,keys = {},[]
        smzap.ls(keys=keys)
        for key in keys:
            logsm[int(key,base=16)] = smzap.lookup(key,fmt='num')[0]
        
        keys = logsm.keys()
        keys.sort()
        self._info['logsm'] = [logsm[k] for k in keys]
        
        self.logsm = logsm
        self.reset()
    
    def reset(self):
        self.rt.free(RangeSeg(0,self._info['length']), initial=True)
        for smobj in self.replay_table:
            self.replay_table[smobj]['decoder'].reset()
        self.replayed_txg = 0
    
    def replay(self, smobj, out=sys.stdout):
        decoder = self.open_sm(smobj)['decoder']
        
        curr_txg,repeat_txg = -1,-1
        sms = decoder.next_txg_bump()
        for sm in sms:
            if 'txg' in sm:
                if curr_txg != sm['txg']:
                    assert(curr_txg < sm['txg'])
                    if curr_txg > self.replayed_txg:
                        self.replayed_txg = curr_txg
                    curr_txg = sm['txg']
                    continue
            
            assert(curr_txg >= 0)
            if curr_txg <= self.replayed_txg:
                if curr_txg != repeat_txg:
                    repeat_txg = curr_txg
                    print('##### Repeat txg=%d #####' % curr_txg)
                continue
            
            if 'vdev_id' in sm:
                vid = sm['vdev_id']
                if vid is not None and int(vid) != int(self._info['tvd_id']):
                    continue
            
            if 'offset' in sm:
                rs = RangeSeg(sm['offset'], sm['run_len'])
                op = {0:self.rt.alloc, 1:self.rt.free}[sm['maptype']]
                op(rs)
        
        if curr_txg > self.replayed_txg:
            self.replayed_txg = curr_txg
        
        decoder.dump_sm_array(sms, out=out)
        self.rt.dump(out=out)
        
        return not not sms
    
    def replay_done(self, smobj, out=sys.stdout):
        while self.replay(smobj, out=out):
            out.write('\n')
    
    def open_sm(self, smobj):
        if smobj not in self.replay_table:
            sm   = self.spa.mos.get(smobj,type=SpaceMap)
            data = Int.from_bytes_to_list(
                sm.read(0,sm.phys.smp_length), int_size=8)
            self.replay_table[smobj] = {
                'sm'      : sm,
                'decoder' : SpaceMapDecoder(data),
            }
        return self.replay_table[smobj]
    
    def dump(self):
        keyorder = ['tvd_id', 'ms_id', 'start', 'length', 'smobj', 'logsm']
        keylen,output = max([len(k) for k in self._info]),[]
        
        for k in keyorder:
            if k in self._info:
                output.append('%-*s : %s' % (keylen, k, str(self._info[k])))
        
        for k in self._info:
            if k not in keyorder:
                output.append('%-*s : %s' % (keylen, k, str(self._info[k])))
        
        print('\n'.join(output))
