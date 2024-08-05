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
    
    def read_label(self, label_index=0):
        return self.read(self._label_off(label_index), self.LABEL_SIZE)
    
    def read_nvpair(self, label_index=0):
        return self.read(self._nvpair_off(label_index), self.NVPAIR_LEN)
    
    def read_uberblock(self, label_index=0):
        return self.read(self._uberblock_off(label_index), self.UBERBLOCK_LEN)
    
    def _label_off(self, label_index):
        assert(label_index in range(4))
        assert(self._size > 4 * self.LABEL_SIZE)
        
        offset = self.LABEL_SIZE * label_index
        if label_index >= 2:
            offset += self._size - 4 * self.LABEL_SIZE
        return offset
    
    def _nvpair_off(self, label_index):
        return self._label_off(label_index) + self.NVPAIR_OFF
    
    def _uberblock_off(self, label_index):
        return self._label_off(label_index) + self.UBERBLOCK_OFF
    
    LABEL_SIZE = 256*1024
    NVPAIR_OFF,NVPAIR_LEN = 16*1024, (128-16)*1024
    UBERBLOCK_OFF,UBERBLOCK_LEN = 128*1024, (256-128)*1024
    