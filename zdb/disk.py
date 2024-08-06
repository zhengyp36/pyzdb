# -*- coding:utf-8 -*-

from . import core
from . import utils
from . import nvlist
from . import uberblock

class Disk(core.Disk):
    @property
    def size(self):
        return utils.StorageSize(self._size)
    
    @property
    def sector_size(self):
        return utils.StorageSize(self._sector_size)
    
    @property
    def capacity(self):
        return utils.StorageSize(self._capacity)
    
    @property
    def is_zfs(self):
        return self.pickup_label_nvpairs() is not None
    
    def pickup_label_nvpairs(self, label_index=None):
        if label_index is not None:
            indexes = [label_index]
        else:
            indexes = range(self.LABEL_NUM)
        
        for i in indexes:
            nvl = self._parse_label_nvpairs(label_index=i)
            if nvl:
                return nvl
        return None
    
    def read_label(self, label_index=0):
        return self.read(self._label_off(label_index), self.LABEL_SIZE)
    
    def read_nvpair(self, label_index=0):
        return self.read(self._nvpair_off(label_index), self.NVPAIR_LEN)
    
    def read_uberblocks(self, label_index=0):
        return self.read(self._uberblock_off(label_index), self.UBERBLOCK_LEN)
    
    def read_uberblock(self, label_index=0, uberblock_index=0, nvpairs=None):
        nvpairs = self._get_nvpairs(nvpairs)
        sz = self.uberblock_size(nvpairs=nvpairs)
        off = self._uberblock_off(label_index=label_index) + sz*uberblock_index
        return self.read(off, sz)
    
    def pickup_uberblock(self, label_index=0, uberblock_index=0, nvpairs=None):
        ub = uberblock.UberBlock.from_bins(
            self.read_uberblock(
                label_index=label_index,
                uberblock_index=uberblock_index,
                nvpairs=nvpairs
            )
        )
        
        ub.label_index = label_index
        ub.uberblock_index = uberblock_index
        return ub
    
    def pickup_all_uberblocks(self, nvpairs=None, verify=False):
        nvpairs = self._get_nvpairs(nvpairs)
        ub_num = self.uberblock_count(nvpairs=nvpairs)
        real_ub_num = 0
        
        ubs = []
        for label in range(self.LABEL_NUM):
            _ubs = []
            for ubidx in range(ub_num):
                try:
                    _ubs.append(self.pickup_uberblock(
                        label_index=label,
                        uberblock_index=ubidx,
                        nvpairs=nvpairs
                    ))
                except:
                    pass
            _ubs.sort()
            ubs.append(_ubs)
            
            assert(len(_ubs) > 0)
            if verify:
                assert(real_ub_num == 0 or len(_ubs) == real_ub_num)
                real_ub_num = len(_ubs)
        
        if verify:
            for lbl in range(self.LABEL_NUM)[1:]:
                for ub in range(real_ub_num):
                    assert(ubs[lbl][ub].ub_txg == ubs[0][ub].ub_txg)
        
        return ubs
    
    def select_uberblock(self, nvpairs=None):
        nvpairs = self._get_nvpairs(nvpairs)
        ubs = self.pickup_all_uberblocks(nvpairs=nvpairs)
        
        ub = ubs[0][-1]
        for i in range(self.LABEL_NUM)[1:]:
            assert(ubs[i][-1].ub_txg == ub.ub_txg)
        
        return ub
    
    def uberblock_size(self, nvpairs=None):
        nvpairs = self._get_nvpairs(nvpairs)
        ashift = min(
            max(nvpairs['vdev_tree']['ashift'],self.UBERBLOCK_SHIFT),
            self.MAX_UBERBLOCK_SHIFT
        )
        return 1 << ashift
    
    def uberblock_count(self, nvpairs=None):
        sz = self.uberblock_size(nvpairs=nvpairs)
        if sz is not None:
            return self.UBERBLOCK_LEN // sz
        else:
            return None
    
    def _label_off(self, label_index):
        assert(label_index in range(self.LABEL_NUM))
        assert(self._size > self.LABEL_NUM * self.LABEL_SIZE)
        
        offset = self.LABEL_SIZE * label_index
        if label_index >= self.LABEL_NUM // 2:
            offset += self._size - self.LABEL_NUM * self.LABEL_SIZE
        return offset
    
    def _nvpair_off(self, label_index):
        return self._label_off(label_index) + self.NVPAIR_OFF
    
    def _uberblock_off(self, label_index):
        return self._label_off(label_index) + self.UBERBLOCK_OFF
    
    def _parse_label_nvpairs(self, label_index):
        try:
            nvl = nvlist.NVList.parse(self.read_nvpair(label_index))
            for n in self.NVPAIR_KEYS:
                if n not in nvl:
                    return None
            return nvl
        except:
            return None
    
    def _get_nvpairs(self, nvpairs):
        if nvpairs is None:
            nvpairs = self.pickup_label_nvpairs()
            if nvpairs is None:
                return None
        return nvpairs
    
    LABEL_SIZE,LABEL_NUM = 256*1024,4
    NVPAIR_OFF,NVPAIR_LEN = 16*1024, (128-16)*1024
    UBERBLOCK_OFF,UBERBLOCK_LEN = 128*1024, (256-128)*1024
    UBERBLOCK_SHIFT,MAX_UBERBLOCK_SHIFT = 10,13
    
    NVPAIR_KEYS = [
        'version', 'name', 'state', 'txg', 'pool_guid',
        'top_guid', 'guid', 'vdev_children', 'vdev_tree'
    ]
