import sys
from zdb import *
mgr = SpaManager()
spa = mgr.open_pool('poola')
sm_zap_obj = spa.rdir.lookup('com.delphix:log_spacemap_zap',fmt='num')[0]
sm_zap = spa.mos.get(sm_zap_obj,type=Zap)
if len(sys.argv[1:]) > 0:
    for txg in sys.argv[1:]:
        txg = int(txg)
        key = hex(txg)[2:]
        obj = sm_zap.lookup(key,fmt='num')[0]
        sm = SpaceMapPhys(spa.mos.get(obj).dnphys.dn_bonus)
        print('txg=%s(%s), obj=%d(%d), length=%d' % (
            txg, hex(txg), obj, sm.smp_object, sm.smp_length
        ))
else:
    sm_zap.ls()
