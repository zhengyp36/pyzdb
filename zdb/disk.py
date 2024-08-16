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
    
    @classmethod
    def convert_buffer(cls, buffer=None, size=0):
        if size == 0:
            size = len(buffer)
        assert(size > 0)
        
        if buffer is None:
            buf = memoryview(bytearray(size))
        else:
            buf = memoryview(buffer)[:size]
            assert(len(buf) == size)
        
        return buf
    
    def read(self, offset, size=0, buffer=None, diskOff=0):
        buf = self.convert_buffer(buffer=buffer,size=size)
        super(type(self),self).read(diskOff+offset,buf)
        return buf
    
    def read_nvpairs(self, label_index=0):
        off = self._label_off(label_index=label_index)
        NVP_START,NVP_SIZE = 16*1024, 112*1024
        return self.read(off+NVP_START, size=NVP_SIZE)
    
    def read_uberblock(self, label_index=0):
        off = self._label_off(label_index=label_index)
        UB_START,UB_SIZE = 128*1024, 128*1024
        return self.read(off+UB_START, size=UB_SIZE)
    
    def _label_off(self, label_index):
        assert(self._size > self.ZFS_DISK_MIN_SIZE)
        assert(0 <= label_index < self.ZFS_LABEL_NUM)
        
        off = label_index * self.ZFS_LABEL_SIZE
        if label_index >= self.ZFS_LABEL_NUM/2:
            off += self._size - self.ZFS_LABEL_NUM * self.ZFS_LABEL_SIZE
        return off
    
    ZFS_LABEL_NUM     = 4
    ZFS_LABEL_SIZE    = 256*1024
    ZFS_RESRV_SIZE    = int(3.5*1024*1024)
    ZFS_DISK_MIN_SIZE = ZFS_LABEL_NUM * ZFS_LABEL_SIZE + ZFS_RESRV_SIZE
