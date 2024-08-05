#-*- coding:utf-8 -*-

import os
import sys
import zdb

'''
$ zpool create poolx        \
    raidz /dev/sdb /dev/sdc \
    raidz /dev/sdd /dev/sde \
    raidz /dev/sdf /dev/sdg
'''

def usage(appname):
    print('usage: %s -nvlist <disk_path> [<label_index> ...]' % appname)
    print('       %s -vdev <disk_path> [<disk_path_1> ...]' % appname)

if __name__ == '__main__':
    appname = os.path.basename(sys.argv[0])
    
    args,options = [],set()
    for arg in sys.argv[1:]:
        if arg.startswith('-'):
            options.add(arg)
        else:
            args.append(arg)
    
    options = list(options)
    if len(options) != 1 or options[0] not in ['-nvlist', '-vdev'] or not args:
        usage(appname)
        sys.exit(0)
    
    if options[0] == '-nvlist':
        disk = zdb.Disk(args[0])
        
        labels = args[1:]
        if not labels:
            labels = ['0']
        
        print("Disk '%s' is zfs: %s" % (disk.path, disk.is_zfs))
        
        for str_label_index in labels:
            label_index = int(str_label_index)
            print('#'*80)
            print('Dump NVList in label %d' % label_index)
            print('#'*80)
            zdb.NVList.parse(disk.read_nvpair(label_index)).dump()
            print('#'*80)
            print('')
    
    elif options[0] == '-vdev':
        rvds = zdb.VDev.parse(args)
        for key in rvds:
            print('#' * 10 + 'Dump rvd[%s] ...' % key)
            rvds[key].dump()
