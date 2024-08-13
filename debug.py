# -*- coding:utf-8 -*-

import sys
import zdb

def debug(spa):
    sep = '-' * 80
    print(sep)
    print('POOL: %s' % spa.name)
    print(sep)
    
    print('disks')
    for vd in spa.rvd.leaves:
        print('  %s' % vd.path)
    print(sep)
    print(spa.uberblock)
    print(sep)
    print(spa.uberblock.ub_rootbp)
    print('')
    
    rds_obj = spa.objdir.lookup('root_dataset',fmt='num')['value'][0]
    print('root_dataset objid = ' + str(rds_obj))
    dn = spa.meta_os.get(rds_obj)
    zap = spa.meta_os.get(spa.dsldir.dd_phys.dd_child_dir_zapobj,type=zdb.Zap)
    zap.ls()
    print('')

if __name__ == '__main__':
    argv = sys.argv[1:]
    if len(argv) > 0 and argv[0] == 'ALL':
        disks = []
        argv = argv[1:]
    else:
        disks = [
            '/dev/sdb1', '/dev/sdc1',
            '/dev/sdd1', '/dev/sde1',
            '/dev/sdf1', '/dev/sdg1',
            '/dev/sdh1',
        ]
    mgr = zdb.SpaManager(disks=disks)
    
    if len(argv) == 0:
        mgr.ls()
    else:
        for name in argv:
            spa = mgr.open_pool(name)
            if spa:
                debug(spa)
            else:
                print('Failed to open pool %s' % name)

else:
    print('NAME=%s' % __name__)
    disks = [ '/dev/sdh1' ]
    mgr = zdb.SpaManager(disks)
    spa = mgr.open_pool('poola')
    zap = spa.meta_os.get(spa.dsldir.dd_phys.dd_child_dir_zapobj,type=zdb.Zap)
    zap.ls()
