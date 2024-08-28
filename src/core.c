#include "internal.h"

static PyObject *create_module_impl(void);

typedef struct {
	const char *name;
	PyTypeObject *tp;
} type_pair_t;

#define TYPE_PAIR_ENT(n,p) { .name = n, .tp = p }
#define TYPE_PAIR_NULL TYPE_PAIR_ENT(NULL, NULL)

static type_pair_t type_table[] = {
	TYPE_PAIR_ENT("Disk",       &zdbcore_DiskType),
	TYPE_PAIR_ENT("BTree",      &zdbcore_BTreeType),
	TYPE_PAIR_ENT("BTreeIndex", &zdbcore_BTreeIndexType),
	TYPE_PAIR_NULL
};

static void
submod_init(void)
{
	zdbcore_compress_init();
	zdbcore_btree_init();
}

static void
submod_fini(void)
{
	zdbcore_btree_fini();
	zdbcore_compress_fini();
}

static PyObject *
zdbcore_init_impl(void)
{
	submod_init();

	for (type_pair_t *tp = type_table; tp->name; tp++) {
		if (PyType_Ready(tp->tp) < 0) {
			submod_fini();
			return (NULL);
		}
	}

	PyObject *m = create_module_impl();
	if (!m) {
		submod_fini();
		return (NULL);
	}

	for (type_pair_t *tp = type_table; tp->name; tp++) {
		Py_INCREF(tp->tp);
		PyModule_AddObject(m, tp->name, (PyObject*)tp->tp);
	}

	return (m);
}

#ifdef IS_PY3K
PyMODINIT_FUNC PyInit_core(void) { return (zdbcore_init_impl()); }
#else
PyMODINIT_FUNC initcore(void) { zdbcore_init_impl(); }
#endif

#define ZDBCORE_COMPRESS_DOC \
"core.compress(compr_type, src, dst) -> int\n\n" \
"    compr_type : tell which algorithm to be used to compress data.\n" \
"    src        : an object of memoryview, storing data of user.\n" \
"    dst        : an writable object of memoryview with length shorter\n" \
"                 than src's, to store the compressed data.\n" \
"    return-val : the length of compressed data in dst, shorter than src's.\n"

#define ZDBCORE_DECOMPRESS_DOC \
"core.decompress(compr_type, src, dst) -> None\n\n" \
"    compr_type : tell which algorithm to be used to decompress data.\n" \
"    src        : an object of memoryview, holding data to be decompressed.\n" \
"    dst        : an writable object of memoryview, length of which is\n" \
"                 longer than src's, to store decompressed data.\n" \
"    return-val : None.\n"

static PyMethodDef zdbcore_methods[] = {
	{
		"compress",
		zdbcore_compress,
		METH_VARARGS,
		ZDBCORE_COMPRESS_DOC
	},{
		"decompress",
		zdbcore_decompress,
		METH_VARARGS,
		ZDBCORE_DECOMPRESS_DOC
	}, {NULL}
};

#define ZDB_CORE_DOCS "core functions for zfs debugger"

static PyObject *
create_module_impl(void)
{
#ifdef IS_PY3K // python 3.x
	static struct PyModuleDef zdbcore_module = {
		PyModuleDef_HEAD_INIT,
		.m_name = "core",
		.m_doc = ZDB_CORE_DOCS,
		.m_size = -1,
		.m_methods = zdbcore_methods
	};
	return (PyModule_Create(&zdbcore_module));
#else // python 2.x
	return (Py_InitModule3("core", zdbcore_methods, ZDB_CORE_DOCS));
#endif // python 2.x
}
