# -*- coding:utf-8 -*-

from . import core
from . import utils
from . import nvlist

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
        for i in range(self.LABEL_NUM):
            if self._is_valid_label(i):
                return True
        return False
    
    def read_label(self, label_index=0):
        return self.read(self._label_off(label_index), self.LABEL_SIZE)
    
    def read_nvpair(self, label_index=0):
        return self.read(self._nvpair_off(label_index), self.NVPAIR_LEN)
    
    def read_uberblock(self, label_index=0):
        return self.read(self._uberblock_off(label_index), self.UBERBLOCK_LEN)
    
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
    
    def _is_valid_label(self, label_index):
        try:
            nvl = nvlist.NVList.parse(self.read_nvpair(label_index))
            for n in self.NVPAIR_KEYS:
                if n not in nvl:
                    return False
            return True
        except:
            return False
    
    LABEL_SIZE,LABEL_NUM = 256*1024,4
    NVPAIR_OFF,NVPAIR_LEN = 16*1024, (128-16)*1024
    UBERBLOCK_OFF,UBERBLOCK_LEN = 128*1024, (256-128)*1024
    
    NVPAIR_KEYS = [
        'version', 'name', 'state', 'txg', 'pool_guid',
        'top_guid', 'guid', 'vdev_children', 'vdev_tree'
    ]
