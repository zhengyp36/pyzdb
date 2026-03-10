# pyzdb internals

This document explains how pyzdb maps ZFS on-disk structures into Python.

---

## Core idea

ZFS is fundamentally:

> a graph of block pointers rooted at the uberblock.

Everything — files, directories, datasets — is reachable by following blkptrs.

pyzdb implements three primitives:

1. Disk access
2. Block pointer resolution
3. On-disk structure decoding

---

## Disk layer

Disks are memory-mapped using C for performance.

Python sees them as byte arrays.

---

## blkptr and DVA

A blkptr contains up to 3 DVAs:

````

(vdev_id, offset, size)

````

pyzdb:
- resolves the vdev through the vdev tree
- maps RAIDZ offsets
- reads physical blocks
- decompresses data

All of this is hidden behind:

```python
reader.read(blkptr)
````

---

## CStruct

Most ZFS on-disk objects are fixed-layout C structs.

pyzdb defines:

```python
class CStruct:
    fields = [
        ("dn_type", U8, 0x00),
        ...
    ]
```

This allows automatic decoding of raw disk bytes into Python objects.

All ZFS types (uberblock, dnode, blkptr, zap, etc.) are defined this way.

---

## Dnodes and indirect blocks

A dnode contains `dn_blkptr[]`.

These may point to:

* data blocks (level 0)
* indirect blocks (level > 0)

pyzdb implements the same block-tree traversal used by ZFS:

```
logical offset → blkid → indirect → data block
```

The user only calls:

```python
dnode.read(offset, size)
```

---

## ZAP

ZAP is ZFS’s on-disk dictionary format.

It is used for:

* directories
* object lookup
* metadata

pyzdb implements both microzap and fatzap and exposes them as Python dict-like objects.

---

## Why this works

pyzdb does not guess.

It:

* reads bytes from disk
* decodes them according to ZFS layout
* follows blkptrs

This ensures the on-disk truth is always the authority.
