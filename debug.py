# -*- coding:utf-8 -*-

import sys
import zdb

def debug_zpl(spa):
    master = spa.rds.myos.get(1, type=zdb.Zap)
    print('Master>>>')
    master.ls()
    print('')
    sa = spa.rds.myos.get(master.lookup('SA_ATTRS',fmt='num')[0],type=zdb.Zap)
    sa.ls()
    print('')
    layout = spa.rds.myos.get(sa.lookup('LAYOUTS',fmt='num')[0],type=zdb.Zap)
    layout.ls()

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
    
    rds_obj = spa.rdir.lookup('root_dataset',fmt='num')[0]
    print('root_dataset objid = ' + str(rds_obj))
    dn = spa.mos.get(rds_obj)
    zap = spa.mos.get(spa.rdd.phys.dd_child_dir_zapobj,type=zdb.Zap)
    zap.ls()
    print('')
    debug_zpl(spa)
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
    def show_reg(val):
        val = zdb.Int(val)
        return 'num=%d,len=%d,bswap=%d' % (
            val.bit_field( 0,16),
            val.bit_field(24,16),
            val.bit_field(16, 8)
        )
    
    print('NAME=%s' % __name__)
    disks = [ '/dev/sdh1' ]
    mgr = zdb.SpaManager(disks)
    spa = mgr.open_pool('poola')
    zap = spa.mos.get(spa.rdd.phys.dd_child_dir_zapobj,type=zdb.Zap)
    zap.ls()
    
    master = spa.rds.myos.get(1, type=zdb.Zap)
    print('Master>>>')
    master.ls()
    print('')
    print('SA_ATTRS>>>')
    sa = spa.rds.myos.get(master.lookup('SA_ATTRS',fmt='num')[0],type=zdb.Zap)
    sa.ls()
    print('')
    print('LAYOUTS>>>')
    layout = spa.rds.myos.get(sa.lookup('LAYOUTS',fmt='num')[0],type=zdb.Zap)
    layout.ls()
    print('')
    print('REGISTRY')
    reg = spa.rds.myos.get(sa.lookup('REGISTRY',fmt='num')[0],type=zdb.Zap)
    reg.ls(fmt=show_reg)
