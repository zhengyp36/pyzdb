# pyzdb — ZFS on-disk explorer in Python

`pyzdb` is a Python-based toolkit for exploring **ZFS on-disk structures directly from raw block devices**.

It allows you to:
- Read ZFS pool metadata without importing the pool
- Parse labels, vdev trees, uberblocks, objsets, dnodes, blkptrs
- Traverse ZFS on-disk structures interactively
- Read file data directly from disk

This project was built to answer one question:

> Can we reconstruct and understand the entire ZFS storage model by reading only what is written on disk?

The answer is yes.

---

## What this project is

`pyzdb` is **not** a wrapper around `zdb`.  
It is a **from-scratch reimplementation of ZFS on-disk traversal** in Python + embedded C.

It directly reads:
- `/dev/sdX` block devices
- ZFS labels
- NVLists
- Uberblocks
- Block pointers
- RAID-Z mappings
- DMU objects

And reconstructs:
- vdev trees
- storage pools
- objsets
- datasets
- directories
- files

---

## Architecture

```

pyzdb/
├── src/        # Embedded C code (disk I/O, checksum, decompression, RAIDZ math)
├── zdb/
│   ├── core/   # Compiled C modules (.so)
│   ├── disk.py
│   ├── spa.py
│   ├── vdev.py
│   ├── dmu.py
│   ├── nvlist.py
│   ├── metaslab.py
│   ├── raidz/
│   ├── utils.py (CStruct, helpers)
│   └── zctypes.py (blkptr, dva, on-disk structs)

````

The core design principle is:

> **Use on-disk data to validate the ZFS model, not the other way around.**

---

## Build

```bash
$ make
````

This builds the embedded C components into shared libraries used by Python.

---

## Quick example

```python
from zdb import *

mgr = SpaManager()
fs1 = mgr.open_ds('poolx/fs1')

f = fs1.rootdir.get('test.txt')
data = fs1.os.spa.reader.read(f.dnphys.dn_blkptr[0])
print(data)
```

This reads the file **directly from disk**, not via the OS.

---

## Documentation

### English

* `docs/en/demo.md` — Step-by-step disk-level walkthrough
* `docs/en/internals.md` — Internal architecture and data model

### Chinese

* `docs/zh/pyzdb 演示.pdf` — 《pyzdb 工具演示》
* `docs/zh/pyzdb 技术说明书.pdf` — 《pyzdb 技术说明书》

---

## Status

This is a **research-grade engineering tool**.

It focuses on:

* correctness
* transparency
* disk-level observability

It does not focus on:

* safety
* pool import/export
* error recovery
* production hardening

---

## Why this exists

ZFS documentation and code explain parts of the system, but it is difficult to form a **complete mental model**.

`pyzdb` was built to bridge that gap by making every on-disk structure directly visible and inspectable.

---

## License

pyzdb is MIT licensed. See [LICENSE](LICENSE).

Some C source files under `src/` are adapted from [OpenZFS](https://github.com/openzfs/zfs) and retain their original CDDL license headers. Some definitions in pyzdb header files are derived from OpenZFS source and are noted in the file header comments.

---

## Discussion

This project was introduced to the OpenZFS community here:

[openzfs/zfs#18340 — pyzdb: a Python+C toolkit for exploring ZFS on-disk structures from raw block devices](https://github.com/openzfs/zfs/discussions/18340)

Feedback and questions are welcome in that thread.
