#include "internal.h"
#include <zdb/disk.h>

typedef struct {
	PyObject_HEAD
	disk_t disk;
} zdbcore_DiskObject;

static PyObject *
zdbcore_Disk_new(PyTypeObject *type, PyObject *args, PyObject *kwargs)
{
	zdbcore_DiskObject *self = (zdbcore_DiskObject*)type->tp_alloc(type, 0);
	if (!self)
		disk_init(&self->disk);
	return ((PyObject*)self);
}

static int
zdbcore_Disk_init(zdbcore_DiskObject *self, PyObject *args, PyObject *kwargs)
{
	char *path;
	if (!PyArg_ParseTuple(args, "s", &path))
		return (-1);

	char *err;
	if (disk_open(&self->disk, path, &err) < 0) {
		PyErr_SetString(PyExc_OSError, err);
		disk_err_free(&err);
		return (-1);
	}

	return (0);
}

static void
zdbcore_Disk_dealloc(zdbcore_DiskObject *self)
{
	disk_close(&self->disk);
	Py_TYPE(self)->tp_free((PyObject*)self);
}

static PyObject *
zdbcore_Disk_get_path(zdbcore_DiskObject *self, void *closure)
{
	if (self->disk.path)
		return (PY_STR_FROM(self->disk.path));
	else
		Py_RETURN_NONE;
}

static PyObject *
zdbcore_Disk_readonly(zdbcore_DiskObject *self, void *closure)
{
	return (PyBool_FromLong(self->disk.readonly));
}

static PyObject *
zdbcore_Disk_get_sector_size(zdbcore_DiskObject *self, void *closure)
{
	return (PY_INT_FROM(self->disk.sector_size));
}

static PyObject *
zdbcore_Disk_get_size(zdbcore_DiskObject *self, void *closure)
{
	return (PY_INT_FROM(self->disk.size));
}

static PyObject *
zdbcore_Disk_get_capacity(zdbcore_DiskObject *self, void *closure)
{
	return (PY_INT_FROM(self->disk.capacity));
}

static PyObject *
zdbcore_Disk_read(zdbcore_DiskObject *self, PyObject *args)
{
	long offset;
	PyObject *pbuf;
	if (!PyArg_ParseTuple(args, "lO", &offset, &pbuf))
		return (NULL);

	Py_buffer buf;
	if (PyObject_GetBuffer(pbuf, &buf, PyBUF_WRITABLE) == -1) {
		PyErr_SetString(PyExc_ValueError,
		    "Failed to get writable buffer");
		return (NULL);
	}

	int err = -1;
	do {
		if (buf.readonly) {
			PyErr_SetString(PyExc_ValueError,
			    "Buffer is not writable");
			break;
		}

		unsigned long long u_off = offset;
		unsigned int u_len = buf.len;
		if (u_off > self->disk.size ||
		    self->disk.size - u_off < u_len) {
			PyErr_SetString(PyExc_IOError, "Read out-of-range");
			break;
		}

		if (!self->disk.addr) {
			PyErr_SetString(PyExc_OSError, "Disk not mapped");
			break;
		}

		memcpy(buf.buf, self->disk.addr + u_off, u_len);
		err = 0;
	} while (0);

	PyBuffer_Release(&buf);
	if (err)
		return (NULL);
	else
		Py_RETURN_NONE;
}

static PyGetSetDef zdbcore_Disk_getseters[] = {
	PROPERTY_RDONLY(
	    "path",
	    "disk path",
	    zdbcore_Disk_get_path),
	PROPERTY_RDONLY(
	    "readonly",
	    "disk is readonly",
	    zdbcore_Disk_readonly),
	PROPERTY_RDONLY(
	    "_sector_size",
	    "disk sector size",
	    zdbcore_Disk_get_sector_size),
	PROPERTY_RDONLY(
	    "_size",
	    "disk size",
	    zdbcore_Disk_get_size),
	PROPERTY_RDONLY(
	    "_capacity",
	    "disk capacity",
	    zdbcore_Disk_get_capacity),
	PROPERTY_NULL
};

static PyMethodDef zdbcore_Disk_methods[] = {
	{
		"read",
		(PyCFunction)zdbcore_Disk_read,
		METH_VARARGS,
		"read(offset,length) -> read data from disk, returned as bytes."
	}, {NULL}
};

PyTypeObject zdbcore_DiskType = {
	PyVarObject_HEAD_INIT(NULL, 0)
	.tp_name = "core.Disk",
	.tp_doc = "Disk Object",
	.tp_basicsize = sizeof(zdbcore_DiskObject),
	.tp_flags = Py_TPFLAGS_DEFAULT | Py_TPFLAGS_BASETYPE,
	.tp_init = (initproc)zdbcore_Disk_init,
	.tp_new = zdbcore_Disk_new,
	.tp_dealloc = (destructor)zdbcore_Disk_dealloc,
	.tp_methods = zdbcore_Disk_methods,
	.tp_getset = zdbcore_Disk_getseters,
};
