#-*- coding:utf-8 -*-

import re
import os
import sys

class SimpleStruct(object):
    FIELDS = []
    
    def __init__(self, default_value=0):
        for field in self.FIELDS:
            setattr(self, field, default_value)
    
    def __str__(self):
        s,keylen = [],max([len(f) for f in self.FIELDS])
        
        for field in self.FIELDS:
            val = getattr(self,field)
            if isinstance(val,list):
                val = '--'
            s.append('  %-*s : %s' % (keylen, field, str(val)))
        
        tname = type(self).__name__
        return tname + '{\n' + '\n'.join(s) + '\n}'
    
    __repr__ = __str__

class ZIO(SimpleStruct):
    FIELDS = ['io_offset', 'io_size']
    def __init__(self, io_offset=0, io_buffer=bytearray(0)):
        super(type(self),self).__init__()
        self.io_offset = io_offset
        self.io_buffer = memoryview(io_buffer)
        self.io_size = len(io_buffer)

class RaidzMap(SimpleStruct):
    class Row(SimpleStruct):
        FIELDS = [
            'rr_cols',         'rr_scols',       'rr_bigcols',
            'rr_firstdatacol', 'rr_missingdata', 'rr_missingparity',
            'rr_nempty',       'rr_abd_emtpy',   'rr_col',
        ]
        def __init__(self, acols, scols=1):
            super(type(self),self).__init__()
            self.rr_cols = acols
            self.rr_scols = scols
            self.rr_col = [None] * scols
    
    class Column(SimpleStruct):
        FIELDS = [
            'rc_devidx',       'rc_offset',       'rc_size',        'rc_abd',
            'rc_skipped',      'rc_orig_data',    'rc_tried',       'rc_error',
            'rc_force_repair', 'rc_allow_repair', 'rc_need_orig_restore',
        ]
        def __init__(self):
            super(type(self),self).__init__()
            self.rc_abd = []
            self.rc_allow_repair = 1
            self.rc_need_orig_restore = False
    
    FIELDS = ['rm_nrows', 'rm_row', 'rm_nskip', 'rm_skipstart']
    def __init__(self, rm_nrows=1):
        super(type(self),self).__init__()
        self.rm_nrows = rm_nrows
        self.rm_row = [None] * rm_nrows
    
    @classmethod
    def alloc(cls, zio, ashift, dcols, nparity):
        '''Import from C-code: vdev_raidz_map_alloc()'''
        roundup = lambda x,y : (x+y-1) // y * y
        
        b = zio.io_offset >> ashift
        s = zio.io_size >> ashift
        f = b % dcols
        o = (b // dcols) << ashift
        
        rm = cls(rm_nrows=1)
        
        q = s // (dcols - nparity)
        r = s - q * (dcols - nparity)
        bc = int(r!=0) * (r + nparity)
        tot = s + nparity * (q + int(r!=0) * 1)
        
        if q == 0:
            acols = bc
            scols = min(dcols, roundup(bc, nparity+1))
        else:
            acols = dcols
            scols = dcols
        
        assert(acols <= scols)
        
        rr = rm.rm_row[0] = cls.Row(acols,scols)
        rr.rr_bigcols = bc
        rr.rr_firstdatacol = nparity
        
        asize = 0
        for c in range(scols):
            rc = rr.rr_col[c] = cls.Column()
            
            col = f + c
            coff = o
            if col >= dcols:
                col -= dcols
                coff += 1 << ashift
            
            rc.rc_devidx = col
            rc.rc_offset = coff
            if c >= acols:
                rc.rc_size = 0
            elif c < bc:
                rc.rc_size = (q+1) << ashift
            else:
                rc.rc_size = q << ashift
            
            asize += rc.rc_size
        
        assert(asize == (tot << ashift))
        rm.rm_nskip = roundup(tot, nparity+1) - tot
        rm.rm_skipstart = bc
        
        assert(rr.rr_cols >= 2)
        assert(rr.rr_col[0].rc_size == rr.rr_col[1].rc_size)
        
        if rr.rr_firstdatacol == 1 and (zio.io_offset & (1<<20)) != 0:
            devidx = rr.rr_col[0].rc_devidx
            o = rr.rr_col[0].rc_offset
            rr.rr_col[0].rc_devidx = rr.rr_col[1].rc_devidx
            rr.rr_col[0].rc_offset = rr.rr_col[1].rc_offset
            rr.rr_col[1].rc_devidx = devidx
            rr.rr_col[1].rc_offset = o
            
            if rm.rm_skipstart == 0:
                rm.rm_skipstart = 1
        
        cls.alloc_write(zio, rm, ashift)
        
        return rm
    
    @classmethod
    def alloc_write(cls, zio, rm, ashift):
        '''Import from C-code: vdev_raidz_map_alloc_write()'''
        
        assert(rm.rm_nrows == len(rm.rm_row) == 1)
        rr = rm.rm_row[0]
        
        if rm.rm_skipstart < rr.rr_firstdatacol:
            assert(rm.rm_skipstart == 0)
            nwrapped = rm.rm_nskip
        elif rr.rr_scols < (rm.rm_skipstart + rm.rm_nskip):
            nwrapped = (rm.rm_skipstart + rm.rm_nskip) % rr.rr_scols
        else:
            nwrapped = 0
        
        skipped = rr.rr_scols - rr.rr_cols
        
        c = 0
        while c < rr.rr_firstdatacol:
            rc = rr.rr_col[c]
            if c < nwrapped:
                rc.rc_abd.append(cls.alloc_buffer(
                    'parity',
                    rc.rc_size + (1 << ashift)
                ))
                skipped += 1
            else:
                rc.rc_abd.append(cls.alloc_buffer(
                    'parity',
                    rc.rc_size
                ))
            
            c += 1
        
        off = 0
        while c < rr.rr_cols:
            rc = rr.rr_col[c]
            abd = cls.get_data_buffer(zio, off, rc.rc_size)
            if c >= rm.rm_skipstart and skipped < rm.rm_nskip:
                rc.rc_abd.append(abd)
                rc.rc_abd.append(cls.alloc_buffer('align', 1<<ashift))
                skipped += 1
            else:
                rc.rc_abd.append(abd)
            
            off += rc.rc_size
            c += 1
        
        assert(off == zio.io_size)
        assert(skipped == rm.rm_nskip)
    
    @classmethod
    def get_data_buffer(cls, zio, offset, size):
        return {
            'type'   : 'data',
            'buffer' : zio.io_buffer[offset : offset + size],
            'offset' : offset,
            'size'   : size,
            'zio'    : zio,
        }
    
    @classmethod
    def alloc_buffer(cls, type, size):
        return {
            'type'   : type,
            'buffer' : memoryview(bytearray(size)),
            'offset' : 0,
            'size'   : size,
            'zio'    : None,
        }

class RaidzTester(object):
    '''Generate raidz.txt
    1. stap -v -d zfs raidz.stp
    2. dd if=/dev/urandom of=random.dat bs=4096 count=4096
       dd if=random.dat of=/poolx/fs1/random.dat bs=$((16*1024))
    3. copy the output of raidz.stp into file raidz.txt
    '''
    
    @classmethod
    def checkLine(cls, line):
        pat  = '(\d+)'
        pat += '\[(\d+),(\d+),(\d+)\]'
        pat += '\<(\d+):(\d+)\>'
        pat += '=\['
        pat += ','.join(['([-]*\d+):([-]*\d+):([-]*\d+)']*3)
        pat += '\]'
        grp = re.search(pat, line)
        assert(grp)
        arr = [int(i) for i in grp.groups()]
        
        index = arr[0]
        ashift,dcols,nparity = arr[1:4]
        io_offset,io_size = arr[4:6]
        
        ios = []
        for i in range(3):
            pos = 6 + i * 3
            dev,off,sz = arr[pos:pos+3]
            ios.append((dev,off,sz))
        
        zio = ZIO(io_offset,bytearray(io_size))
        rm = RaidzMap.alloc(zio, ashift=ashift, dcols=dcols, nparity=nparity)
        
        s,valid = [],True
        for idx in range(len(rm.rm_row[0].rr_col)):
            devidx,offset,size = ios[idx]
            rc = rm.rm_row[0].rr_col[idx]
            if rc.rc_devidx != devidx or rc.rc_offset != offset or rc.rc_size != size:
                valid = False
            s.append('%d:%d:%d' % (devidx,offset,size))
            idx += 1
        
        if not valid:
            print('index=%d,ashift=%d,dcols=%d,nparity=%d,ios={%s}' % (
                index, ashift, dcols, nparity, '|'.join(s)
            ))
        return valid
    
    @classmethod
    def check(cls, files):
        for infile in files:
            print('Check File: %s ...' % infile)
            valid = True
            for line in open(infile):
                line = line.strip()
                if line:
                    if not cls.checkLine(line):
                        valid = False
            print('Check result: %s' % {
                True : 'success', False : 'failure'
            }[valid])

if __name__ == '__main__':
    if len(sys.argv) == 1:
        print('Usage: %s raidz.txt' % os.path.basename(sys.argv[0]))
    else:
        RaidzTester.check(sys.argv[1:])
