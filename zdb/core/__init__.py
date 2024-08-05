#-*- coding:utf-8 -*-
# wrap for module core

import sys

if sys.version[0] == '2':
    from .v2.core import *
elif sys.version[0] == '3':
    from .v3.core import *
else:
    raise ImportError('Unsupported Python version: %s' % str(sys.version))
