# -*- coding:utf-8 -*-

from .core import Disk

class Disk(Disk):
    @property
    def size(self):
        return utils.StorageSize(self._size)
    
    @property
    def sector_size(self):
        return utils.StorageSize(self._sector_size)
    
    @property
    def capacity(self):
        return utils.StorageSize(self._capacity)
