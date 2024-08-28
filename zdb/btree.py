# -*- coding:utf-8 -*-

from . import core

class BTree(core.BTree):
    def __iter__(self):
        self._index = None
        return self
    iter = __iter__
    
    def __next__(self):
        if self._index is None:
            v,self._index = self.first(True)
        else:
            v = super(type(self),self).next(self._index)
        
        if v is not None:   
            return v
        else:
            raise StopIteration
    next = __next__
