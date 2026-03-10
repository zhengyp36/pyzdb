# pyzdb disk-level walkthrough

This document shows how ZFS structures are discovered and traversed **directly from disk**.

We use a real pool:

```bash
zpool create poolx raidz1 /dev/sdb /dev/sdc /dev/sdd raidz1 /dev/sde /dev/sdf /dev/sdg
zfs create poolx/fs1
echo "hello,world" > /poolx/fs1/test.txt
sync
````

---

## Step 1 — Read a ZFS label

```python
from zdb import *

disk = Disk('/dev/sdb1')
raw = disk.read_nvpairs(label_index=0)
nvlist = NVList.from_bytes(raw)
print(nvlist)
```

Each disk stores:

* pool GUID
* top-vdev GUID
* RAIDZ layout
* children disks

This is how ZFS reconstructs topology.

---

## Step 2 — Build the vdev tree

```python
vdmgr = VDevManager()
vdmgr.scan(['/dev/sdb1'])
vdmgr.scan(['/dev/sdc1', '/dev/sdd1'])
vdmgr.scan(['/dev/sde1', '/dev/sdf1', '/dev/sdg1'])
vdmgr.ls()
```

Output:

```
poolx
  raidz
    sdb1
    sdc1
    sdd1
  raidz
    sde1
    sdf1
    sdg1
```

This gives ZFS its global address space.

---

## Step 3 — Locate uberblocks

Each label contains an array of uberblocks.

```python
def traverse_ub(path):
    disk = Disk(path)
    raw = memoryview(disk.read_uberblock(0))
    ub_sz = 1024
    ubs = []
    for i in range(0, len(raw), ub_sz):
        try:
            ubs.append(UberBlock(raw[i:i+ub_sz]))
        except MagicError:
            pass
    return ubs

ubs = traverse_ub('/dev/sdb1')
best = max(ubs, key=lambda x: x.ub_txg)
print(best)
```

The uberblock with the highest `txg` is the active root.

---

## Step 4 — Read MOS (Meta Object Set)

```python
rvd = vdmgr.lookup('poolx')
rvd.open()

spa = Spa(rvd)
spa.reader = BlkPtrReader(rvd)

mos = ObjSet(spa, best.ub_rootbp)
```

`ub_rootbp` points to the **Meta Object Set**, which is the root of all ZFS metadata.

---

## Step 5 — Read dnodes from MOS

```python
dnsz = DNodePhys.sizeof()
raw = mos.metadn.read(1 * dnsz, dnsz)
dn = DNodePhys(raw)
print(dn)
```

The MOS is itself a dnode whose data is an array of dnodes.
Each of those dnodes represents a ZFS object.

From here:

* datasets
* directories
* files
  are discovered by following dnodes and ZAPs.

---

At this point the entire filesystem can be reconstructed from disk.
