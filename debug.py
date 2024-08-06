#-*- coding:utf-8 -*-

import os
import sys
import zdb

'''
$ zpool create poolx        \
    raidz /dev/sdb /dev/sdc \
    raidz /dev/sdd /dev/sde \
    raidz /dev/sdf /dev/sdg

import zdb
disk = zdb.Disk('/dev/sdh1')
ubraw = disk.read_uberblock()
ub = zdb.UberBlock.from_bins(ubraw)
'''

def usage(appname):
    print('usage: %s -nvlist <disk_path> [<label_index> ...]' % appname)
    print('       %s -uberblock <disk_path>' % appname)
    print('       %s -vdev <disk_path> [<disk_path_1> ...]' % appname)

if __name__ == '__main__':
    OPTIONS = ['-nvlist', '-vdev', '-uberblock']
    appname = os.path.basename(sys.argv[0])
    
    args,options = [],set()
    for arg in sys.argv[1:]:
        if arg.startswith('-'):
            options.add(arg)
        else:
            args.append(arg)
    
    options = list(options)
    if len(options) != 1 or options[0] not in OPTIONS or not args:
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
    
    elif options[0] == '-uberblock':
        line = '-' * 80
        
        assert(len(args) == 1)
        disk = zdb.Disk(args[0])
        
        ubs = disk.pickup_all_uberblocks(verify=True)[0]
        ub = disk.select_uberblock()
        assert(ub.uberblock_index == ubs[-1].uberblock_index)
        
        print(line)
        print('There are %d uberblocks and %dth[txg=%d] the best:' % (
            len(ubs), ub.uberblock_index, ub.ub_txg
        ))
        
        for ub in ubs:
            print(line)
            print('%s uberblock_index=%d' % ('>'*5, ub.uberblock_index))
            print(ub)
            print(ub.ub_rootbp)
        
        print(line)
    
    elif options[0] == '-vdev':
        rvds = zdb.VDev.parse(args)
        for key in rvds:
            print('#' * 10 + 'Dump rvd[%s] ...' % key)
            rvds[key].dump()
