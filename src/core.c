#include "internal.h"

static PyObject *create_module_impl(void);

typedef struct {
	const char *name;
	PyTypeObject *tp;
} type_pair_t;

#define TYPE_PAIR_ENT(n,p) { .name = n, .tp = p }
#define TYPE_PAIR_NULL TYPE_PAIR_ENT(NULL, NULL)

static type_pair_t type_table[] = {
	TYPE_PAIR_ENT("Disk", &zdbcore_DiskType),
	TYPE_PAIR_NULL
};

static PyObject *
zdbcore_init_impl(void)
{
	zdbcore_compress_init();

	for (type_pair_t *tp = type_table; tp->name; tp++) {
		if (PyType_Ready(tp->tp) < 0) {
			zdbcore_compress_fini();
			return (NULL);
		}
	}

	PyObject *m = create_module_impl();
	if (!m) {
		zdbcore_compress_fini();
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
"core.compress(compr_type, usr_data, compr_data) -> int\n\n" \
"    compr_type : tell which algorithm to be used to compress data.\n" \
"    usr_data   : an object of memoryview, storing data of user.\n" \
"    compr_data : an writable object of memoryview with length shorter\n" \
"                 than usr_data's, to store the compressed data.\n" \
"    return-val : the length of compressed data in compr_data, shorter\n" \
"                 than or equal to compr_data's.\n"

#define ZDBCORE_DECOMPRESS_DOC \
"core.decompress(compr_type, usr_data, compr_data) -> None\n\n" \
"    compr_type : tell which algorithm to be used to decompress data.\n" \
"    usr_data   : an writable object of memoryview, to store\n" \
"                 decompressed data.\n" \
"    compr_data : an object of memoryview, holding data to be decompressed.\n" \
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
