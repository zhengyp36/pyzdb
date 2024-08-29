#-*- coding:utf-8 -*-
# wrap for module core

import sys

if sys.version[0] == '2':
    from .v2.core import *
elif sys.version[0] == '3':
    from .v3.core import *
else:
    raise ImportError('Unsupported Python version: %s' % str(sys.version))

class BTree(CBTree):
    def add(self, element=None):
        old,where = self._find(element,True)
        if old is not None:
            self._repeat(old, element)
        if where is None:
            self._add(element)
        else:
            self._add(element, where)
    
    def remove(self, element=None, where=None):
        if element:
            old,idx = self._find(element,True)
            if old is None:
                self._not_found(element)
            self._remove(where=idx)
        else:
            self._remove(where=where)
    
    def clear(self):
        self._clear()
    
    def find(self, element, return_where=False):
        return self._find(element, return_where)
    
    def first(self, return_where=False):
        return self._first(return_where)
    
    def last(self, return_where=False):
        return self._last(return_where)
    
    def get(self, where):
        return self._get(where)
    
    def next(self, where, update_where=True):
        if not update_where:
            where = where.copy()
        return self._next(where)
    
    def prev(self, where, update_where=True):
        if not update_where:
            where = where.copy()
        return self._prev(where)
    
    def tolist(self):
        return self._tolist()
    
    def _not_found(self, element):
        raise Exception('Element <%s> not found' % str(element))
    
    def _repeat(self, old, new):
        raise Exception('Repeat node: old<%s>, new<%s>' % (str(old),str(new)))
