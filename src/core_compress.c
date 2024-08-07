#include "internal.h"
#include <sys/zio_compress.h>

typedef struct {
	int compr_type;
	int usr_writable;
	int compr_writable;
	Py_buffer usr_data;
	Py_buffer compr_data;
} inner_args_t;

static int
get_args(PyObject *args, inner_args_t *inner)
{
	PyObject *usr_data, *compr_data;
	if (!PyArg_ParseTuple(args, "iOO",
	    &inner->compr_type, &usr_data, &compr_data))
		return (-1);

	Py_buffer *bufs[2];
	int buf_cnt = 0;

	do {
		if (PyObject_GetBuffer(usr_data, &inner->usr_data,
		    inner->usr_writable ? PyBUF_WRITABLE : 0) == -1) {
			PyErr_SetString(PyExc_ValueError,
			    "Failed to get usr_data buffer");
			break;
		}
		bufs[buf_cnt++] = &inner->usr_data;

		if (inner->usr_writable && inner->usr_data.readonly) {
			PyErr_SetString(PyExc_ValueError,
			    "usr_data is not writable");
			break;
		}

		if (PyObject_GetBuffer(compr_data, &inner->compr_data,
		    inner->compr_writable ? PyBUF_WRITABLE : 0) == -1) {
			PyErr_SetString(PyExc_ValueError,
			    "Failed to get compr_data buffer");
			break;
		}
		bufs[buf_cnt++] = &inner->compr_data;

		if (inner->compr_writable && inner->compr_data.readonly) {
			PyErr_SetString(PyExc_ValueError,
			    "compr_data is not writable");
			break;
		}

		return (0);
	} while (0);

	while (buf_cnt-- > 0)
		PyBuffer_Release(bufs[buf_cnt]);
	return (-1);
}

static void
put_args(inner_args_t *inner)
{
	PyBuffer_Release(&inner->usr_data);
	PyBuffer_Release(&inner->compr_data);
}

/* core.compress(compr_type, usr_data, compr_data) -> int */
PyObject *
zdbcore_compress(PyObject *self, PyObject *args)
{
	inner_args_t inner;
	inner.usr_writable = 0;
	inner.compr_writable = 1;

	if (get_args(args, &inner))
		return (NULL);

	size_t sz = zio_compress(inner.compr_type,
	    inner.usr_data.buf, inner.compr_data.buf,
	    inner.usr_data.len, inner.compr_data.len);
	if (sz == (size_t)inner.usr_data.len) {
		PyErr_SetString(PyExc_OSError, "Failed to compress");
		put_args(&inner);
		return (NULL);
	}

	return (PY_INT_FROM(sz));
}

/* core.decompress(compr_type, usr_data, compr_data) -> None */
PyObject *
zdbcore_decompress(PyObject *self, PyObject *args)
{
	inner_args_t inner;
	inner.usr_writable = 0;
	inner.compr_writable = 1;

	if (get_args(args, &inner))
		return (NULL);


	int error = zio_decompress(inner.compr_type,
	    inner.usr_data.buf, inner.compr_data.buf,
	    inner.usr_data.len, inner.compr_data.len);
	put_args(&inner);

	if (!error) {
		Py_RETURN_NONE;
	} else {
		PyErr_SetString(PyExc_OSError, "Failed to decompress");
		return (NULL);
	}
}

void
zdbcore_compress_init(void)
{
	zio_compress_init();
}

void
zdbcore_compress_fini(void)
{
	zio_compress_fini();
}
