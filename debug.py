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

python -m pdb debug.py -spa
(Pdb) continue
'''

def debug_nvlist(args):
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

def debug_uberblock(args):
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

def debug_vdev(args):
    rvds = zdb.VDev.parse(args)
    for key in rvds:
        print('#' * 10 + ' Dump rvd[%s] ...' % key)
        rvds[key].dump()
        print('#' * 10 + ' Open rvd[%s] ...' % key)
        if rvds[key].open() and rvds[key].opened:
            print('Open success')
        else:
            print('Open failure')
        print('')

def debug_spa(args):
    mgr = zdb.SpaMgr()
    mgr.scan()
    mgr.ls()
    
    poolx = mgr.lookup('poolx')
    poolx.open()
    poolx.close()
    print(poolx.uberblock)
    print(poolx.uberblock.ub_rootbp)

if __name__ == '__main__':
    table = {
        '-nvlist'    : [debug_nvlist,    1, '<disk_path> [<label_index> ...]' ],
        '-vdev'      : [debug_vdev,      1, '<disk_path> [<disk_path_1> ...]' ],
        '-uberblock' : [debug_uberblock, 1, '<disk_path>'                     ],
        '-spa'       : [debug_spa,       0, ''                                ],
    }
    
    # parse args
    appname = os.path.basename(sys.argv[0])
    args,opts = [],set()
    for arg in sys.argv[1:]:
        if arg.startswith('-'):
            opts.add(arg)
        else:
            args.append(arg)
    
    opts = list(opts)
    if len(opts) != 1 or opts[0] not in table or len(args) < table[opts[0]][1]:
        print('usage:')
        for opt in table:
            print('       %s %s %s' % (appname, opt, table[opt][2]))
        sys.exit(0)
    
    table[opts[0]][0](args)
