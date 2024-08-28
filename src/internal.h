#ifndef _PYTHON_INTERNAL_H
#define _PYTHON_INTERNAL_H

#include <Python.h>

#if PY_MAJOR_VERSION >= 3
#define IS_PY3K
#endif

#ifdef IS_PY3K
#define PY_INT_FROM(n) PyLong_FromLong(n)
#define PY_STR_FROM(s) PyUnicode_FromString(s)
#else
#define PY_INT_FROM(n) PyInt_FromLong(n)
#define PY_STR_FROM(s) PyString_FromString(s)
#endif

#define PROPERTY_RDONLY(name,desc,get) { name, (getter)(get), NULL, desc, NULL }
#define PROPERTY_NULL {NULL}

extern PyTypeObject zdbcore_DiskType;
extern PyTypeObject zdbcore_BTreeType;
extern PyTypeObject zdbcore_BTreeIndexType;

void zdbcore_compress_init(void);
void zdbcore_compress_fini(void);
PyObject *zdbcore_compress(PyObject *self, PyObject *args);
PyObject *zdbcore_decompress(PyObject *self, PyObject *args);

void zdbcore_btree_init(void);
void zdbcore_btree_fini(void);

#endif // _PYTHON_INTERNAL_H
