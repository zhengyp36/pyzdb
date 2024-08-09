# -*- coding:utf-8 -*-

from .utils import StorageSize
from .core import Disk

class Disk(Disk):
    @property
    def size(self):
        return StorageSize(self._size)
    
    @property
    def sector_size(self):
        return StorageSize(self._sector_size)
    
    @property
    def capacity(self):
        return StorageSize(self._capacity)
