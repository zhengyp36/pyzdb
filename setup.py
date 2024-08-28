#-*- encoding: utf-8 -*-

from os import path
from setuptools import setup, Extension

prj_dir = path.abspath(path.dirname(__file__))
abs_path = lambda srcs : [ path.join(prj_dir, p) for p in srcs ]

setup(
    name = 'zdb',
    version = '1.0',
    description = 'zfs debugger',
    ext_modules = [
        Extension(
            'core',
            include_dirs = abs_path([ 'inc' ]),
            libraries = ['z'],
            sources = abs_path([
                'src/core.c',

                # core.Disk
                'src/disk.c',
                'src/core_disk.c',

                # core.Compressor
                'src/compress/lzjb.c',
                'src/compress/gzip.c',
                'src/compress/zle.c',
                'src/compress/lz4.c',
                'src/compress/lz4_zfs.c',
                'src/compress/zio_compress.c',
                'src/core_compress.c',
                
                # core.btree
                'src/btree.c',
                'src/core_btree.c',
            ]),
        )
    ]
)
