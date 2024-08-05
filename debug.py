#-*- coding:utf-8 -*-

import os
import sys
import zdb

if __name__ == '__main__':
    if len(sys.argv) == 1:
        print('usage: %s <disk_path> [<label_index> ...]' %
            os.path.basename(sys.argv[0]))
        sys.exit(0)
    
    disk = zdb.Disk(sys.argv[1])
    
    labels = sys.argv[2:]
    if not labels:
        labels = ['0']
    
    for str_label_index in labels:
        label_index = int(str_label_index)
        print('#'*80)
        print('Dump NVList in label %d' % label_index)
        print('#'*80)
        zdb.NVList.parse(disk.read_nvpair(label_index)).dump()
        print('#'*80)
        print('')
