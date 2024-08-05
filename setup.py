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
            sources = abs_path([
                'src/disk.c',
                'src/core.c',
                'src/core_disk.c',
            ]),
        )
    ]
)
