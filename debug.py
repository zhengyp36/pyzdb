# -*- coding:utf-8 -*-

import sys
import zdb

if __name__ == '__main__':
    vdmgr = zdb.VDevManager()
    vdmgr.scan(sys.argv[1:])
    vdmgr.ls()
