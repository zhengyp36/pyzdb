#include "internal.h"
#include <sys/zio_compress.h>

typedef struct {
	int compr_type;
	int buf_num;
	Py_buffer buf[2]; // buf[0] is src and buf[1] dst
} param_t;

static inline void
put_param(param_t *param)
{
	while (param->buf_num > 0)
		PyBuffer_Release(&param->buf[--(param->buf_num)]);
}

static int
get_param(PyObject *args, param_t *param)
{
	PyObject *src, *dst;
	if (!PyArg_ParseTuple(args, "iOO",
	    &param->compr_type, &src, &dst))
		return (-1);

	param->buf_num = 0;
	do {
		if (PyObject_GetBuffer(src,
		    &param->buf[param->buf_num], 0) == -1) {
			PyErr_SetString(PyExc_ValueError,
			    "Failed to get src buffer");
			break;
		}
		param->buf_num++;

		if (PyObject_GetBuffer(dst,
		    &param->buf[param->buf_num], PyBUF_WRITABLE) == -1) {
			PyErr_SetString(PyExc_ValueError,
			    "Failed to get dst buffer");
			break;
		}
		param->buf_num++;

		if (param->buf[param->buf_num - 1].readonly) {
			PyErr_SetString(PyExc_ValueError,
			    "dst is not writable");
			break;
		}

		return (0);
	} while (0);

	put_param(param);
	return (-1);
}

/* core.compress(compr_type, src, dst) -> int */
PyObject *
zdbcore_compress(PyObject *self, PyObject *args)
{
	param_t param;
	if (get_param(args, &param))
		return (NULL);

	size_t sz = zio_compress(param.compr_type,
	    param.buf[0].buf, param.buf[1].buf,
	    param.buf[0].len, param.buf[1].len);

	PyObject *ret;
	if (sz >= (size_t)param.buf[0].len) {
		PyErr_SetString(PyExc_OSError, "Failed to compress");
		ret = NULL;
	} else {
		ret = PY_INT_FROM(sz);
	}

	put_param(&param);
	return (ret);
}

/* core.decompress(compr_type, src, dst) -> None */
PyObject *
zdbcore_decompress(PyObject *self, PyObject *args)
{
	param_t param;
	if (get_param(args, &param))
		return (NULL);

	int error = zio_decompress(param.compr_type,
	    param.buf[0].buf, param.buf[1].buf,
	    param.buf[0].len, param.buf[1].len);
	put_param(&param);

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
