# -*- coding:utf-8 -*-

from .raidz_impl import ZIO,RaidzMap

class RaidzMapper(object):
    def __init__(self, ashift, dcols, nparity):
        self.ashift = ashift
        self.dcols = dcols
        self.nparity = nparity
    
    def map(self, offset, buffer, include_parity=False):
        rm = RaidzMap.alloc(
            zio     = ZIO(io_offset=offset, io_buffer=buffer),
            ashift  = self.ashift,
            dcols   = self.dcols,
            nparity = self.nparity
        )
        assert(len(rm.rm_row) == 1)
        assert(2 <= len(rm.rm_row[0].rr_col) <= self.dcols)
        
        output = []
        for idx in range(len(rm.rm_row[0].rr_col)):
            rc = rm.rm_row[0].rr_col[idx]
            assert(len(rc.rc_abd) > 0)
            
            if rc.rc_abd[0]['type'] == 'parity':
                assert(len(rc.rc_abd) == 1)
                if include_parity:
                    output.append([
                        rc.rc_devidx,
                        rc.rc_offset,
                        rc.rc_abd[0]['buffer']
                    ])
            elif rc.rc_abd[0]['type'] == 'data':
                assert(len(rc.rc_abd) <= 2)
                if len(rc.rc_abd) == 2:
                    assert(rc.rc_abd[1]['type'] == 'align')
                output.append([
                    rc.rc_devidx,
                    rc.rc_offset,
                    rc.rc_abd[0]['buffer']
                ])
            else:
                raise Exception('Invalid abd type(%s)' % rc.rc_abd[0]['type'])
        
        assert(1 <= len(output) <= self.dcols)
        return output
