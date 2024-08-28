#include "internal.h"
#include <sys/btree.h>

typedef struct {
	PyObject_HEAD
	const zfs_btree_t *	tree;
	zfs_btree_index_t	index;
} zdbcore_BTreeIndexObject;

static PyObject *
zdbcore_BTreeIndex_new(PyTypeObject *type, PyObject *args, PyObject *kwargs)
{
	zdbcore_BTreeIndexObject *self =
	    (zdbcore_BTreeIndexObject*)type->tp_alloc(type, 0);
	if (self) {
		self->tree = NULL;
		memset(&self->index, 0, sizeof(self->index));
	}
	return ((PyObject*)self);
}

static int
zdbcore_BTreeIndex_init(zdbcore_BTreeIndexObject *self,
    PyObject *args, PyObject *kwargs)
{
	return (0);
}

static void
zdbcore_BTreeIndex_dealloc(zdbcore_BTreeIndexObject *self)
{
	Py_TYPE(self)->tp_free((PyObject*)self);
}

static PyObject *
btree_index_clone(zdbcore_BTreeIndexObject *self, PyObject *noargs)
{
	zdbcore_BTreeIndexObject *other = (zdbcore_BTreeIndexObject*)
	    PyObject_New(zdbcore_BTreeIndexObject, &zdbcore_BTreeIndexType);
	if (other) {
		other->tree = self->tree;
		other->index = self->index;
	}
	return ((PyObject*)other);
}

static PyObject *
btree_index_cmp(PyObject *_self, PyObject *_other, int op)
{
	zdbcore_BTreeIndexObject *self = (zdbcore_BTreeIndexObject*)_self;
	if (!PyObject_TypeCheck(_other, Py_TYPE(self)) ||
	    (op != Py_EQ && op != Py_NE)) {
		Py_INCREF(Py_NotImplemented);
		return Py_NotImplemented;
	}

	zdbcore_BTreeIndexObject *other = (zdbcore_BTreeIndexObject*)_other;
	boolean_t equ = (self->tree == other->tree &&
	    self->index.bti_node    == other->index.bti_node &&
	    self->index.bti_offset  == other->index.bti_offset &&
	    self->index.bti_before  == other->index.bti_before);

	if ((op == Py_EQ && equ) || (op == Py_NE && !equ)) {
		Py_RETURN_TRUE;
	} else {
		Py_RETURN_FALSE;
	}
}

static PyMethodDef zdbcore_BTreeIndex_methods[] = {
	{
		"clone",
		(PyCFunction)btree_index_clone,
		METH_NOARGS,
		"clone() -> A copy of the object"
	}, {
		"copy",
		(PyCFunction)btree_index_clone,
		METH_NOARGS,
		"copy() -> A copy of the object"
	}, {NULL}
};

PyTypeObject zdbcore_BTreeIndexType = {
	PyVarObject_HEAD_INIT(NULL, 0)
	.tp_name = "core.BTreeIndex",
	.tp_doc = "BTreeIndex Object",
	.tp_basicsize = sizeof(zdbcore_BTreeIndexObject),
	.tp_flags = Py_TPFLAGS_DEFAULT | Py_TPFLAGS_BASETYPE,
	.tp_init = (initproc)zdbcore_BTreeIndex_init,
	.tp_new = zdbcore_BTreeIndex_new,
	.tp_dealloc = (destructor)zdbcore_BTreeIndex_dealloc,
	.tp_methods = zdbcore_BTreeIndex_methods,
	.tp_richcompare = btree_index_cmp,
};

PyObject *
PyBTreeIndex_FromIndex(const zfs_btree_t *tree, const zfs_btree_index_t *index)
{
	if (index->bti_node == NULL)
		Py_RETURN_NONE;

	zdbcore_BTreeIndexObject *self = (zdbcore_BTreeIndexObject*)
	    PyObject_New(zdbcore_BTreeIndexObject, &zdbcore_BTreeIndexType);
	if (self) {
		self->tree = tree;
		self->index = *index;
	}

	return ((PyObject*)self);
}

typedef struct {
	PyObject_HEAD
	zfs_btree_t	tree;
	PyTypeObject *	type;
	PyObject *	cmp;
	int		cmp_error;
	int		tree_created;
} zdbcore_BTreeObject;

static long
py_long_as(PyObject *result)
{
#ifdef IS_PY3K
	return (PyLong_AsLong(result));
#else // Python-2.x
	if (PyInt_Check(result))
		return (PyInt_AsLong(result));
	else if (PyLong_Check(result))
		return (PyLong_AsLong(result));
	else {
		PyErr_SetString(PyExc_TypeError, "Expected an int or long");
		return (-1);
	}
#endif
}

typedef struct {
	PyObject *obj;
} BTreeNode;

static int
btree_node_cmp(const void *_n1, const void *_n2, void *arg)
{
	zdbcore_BTreeObject *bto = (zdbcore_BTreeObject*)arg;
	const BTreeNode *n1 = (const BTreeNode*)_n1;
	const BTreeNode *n2 = (const BTreeNode*)_n2;

	PyObject *result = PyObject_CallFunctionObjArgs(
	    bto->cmp, n1->obj, n2->obj, NULL);
	if (result == NULL) {
		bto->cmp_error = -1;
		return (0);
	}

	long cmp_result = py_long_as(result);
	if (cmp_result == -1 && PyErr_Occurred())
		bto->cmp_error = -1;
	Py_DECREF(result);

	return (bto->cmp_error ? 0 : (int)cmp_result);
}

static void
btree_clear(zdbcore_BTreeObject *self)
{
	BTreeNode *n;
	zfs_btree_index_t *cookie = NULL;
	while ((n = zfs_btree_destroy_nodes(&self->tree, &cookie)))
		Py_DECREF(n->obj);
	zfs_btree_destroy(&self->tree);
}

static PyObject *
zdbcore_BTree_new(PyTypeObject *type, PyObject *args, PyObject *kwargs)
{
	zdbcore_BTreeObject *self =
	    (zdbcore_BTreeObject*)type->tp_alloc(type, 0);
	if (!self) {
		memset(&self->tree, 0, sizeof(self->tree));
		self->cmp = NULL;
		self->cmp_error = 0;
	}
	return ((PyObject*)self);
}

static int
zdbcore_BTree_init(zdbcore_BTreeObject *self, PyObject *args, PyObject *kwargs)
{
	PyObject *type, *cmp;
	if (!PyArg_ParseTuple(args, "OO", &type, &cmp))
		return (-1);

	if (!PyType_Check(type)) {
		PyErr_SetString(PyExc_TypeError,
		    "Expected a object type but not instance");
		return (-1);
	}

	if (!PyCallable_Check(cmp)) {
		PyErr_SetString(PyExc_TypeError, "Expected a callable object");
		return (-1);
	}

	Py_INCREF(type);
	Py_INCREF(cmp);
	self->type = (PyTypeObject*)type;
	self->cmp = cmp;
	self->tree_created = 1;
	zfs_btree_create(&self->tree, btree_node_cmp, self, sizeof(BTreeNode));

	return (0);
}

static void
zdbcore_BTree_dealloc(zdbcore_BTreeObject *self)
{
	if (self->type) {
		Py_DECREF((PyObject*)self->type);
		self->type = NULL;
	}

	if (self->cmp) {
		Py_DECREF(self->cmp);
		self->cmp = NULL;
	}

	if (self->tree_created) {
		btree_clear(self);
		self->tree_created = 0;
	}

	Py_TYPE(self)->tp_free((PyObject*)self);
}

static PyObject *
zdbcore_BTree_add(zdbcore_BTreeObject *self, PyObject *args, PyObject *kwargs)
{
	PyObject *elem = NULL, *_where = NULL;
	char *kwlist[] = { "element", "where", NULL };
	if (!PyArg_ParseTupleAndKeywords(
	    args, kwargs, "O|O", kwlist, &elem, &_where))
		return (NULL);

	if (!PyObject_TypeCheck(elem, self->type)) {
		PyErr_Format(PyExc_TypeError,
		    "Expected type '%s' but received type '%s'",
		    self->type->tp_name, Py_TYPE(elem)->tp_name);
		return (NULL);
	}

	if (_where && PyObject_TypeCheck(_where, &zdbcore_BTreeIndexType)) {
		PyErr_Format(PyExc_TypeError,
		    "Expected type '%s' but received type '%s'",
		    zdbcore_BTreeIndexType.tp_name, Py_TYPE(_where)->tp_name);
		return (NULL);
	}

	zdbcore_BTreeIndexObject *where = (zdbcore_BTreeIndexObject*)_where;
	if (where && where->tree != &self->tree) {
		PyErr_SetString(PyExc_ValueError,
		    "The argument 'where' does not belong to this tree.");
		return (NULL);
	}

	BTreeNode node = { .obj = elem };
	if (where)
		zfs_btree_add_idx(&self->tree, &node, &where->index);
	else
		zfs_btree_add(&self->tree, &node);

	Py_RETURN_NONE;
}

static PyObject *
zdbcore_BTree_remove(zdbcore_BTreeObject *self, PyObject *args)
{
	PyObject *arg;
	if (!PyArg_ParseTuple(args, "O", &arg))
		return (NULL);

	zdbcore_BTreeIndexObject *where = NULL;
	if (PyObject_TypeCheck(arg, &zdbcore_BTreeIndexType)) {
		zdbcore_BTreeIndexObject *tmp = (zdbcore_BTreeIndexObject*)arg;
		if (tmp->tree == &self->tree)
			where = tmp;
	}

	PyObject *elem = NULL;
	if (!where && PyObject_TypeCheck(arg, self->type))
		elem = arg;

	if (where) {
		zfs_btree_remove_idx(&self->tree, &where->index);
		Py_RETURN_NONE;
	} else if (elem) {
		BTreeNode n = { .obj = elem };
		zfs_btree_remove(&self->tree, &n);
		Py_RETURN_NONE;
	} else {
		PyErr_Format(PyExc_TypeError,
		    "Expected type '%s' or '%s' but not '%s'",
		    zdbcore_BTreeIndexType.tp_name,
		    self->type->tp_name,
		    Py_TYPE(arg)->tp_name);
		return (NULL);
	}
}

static PyObject *
zdbcore_BTree_clear(zdbcore_BTreeObject *self, PyObject *noargs)
{
	btree_clear(self);
	Py_RETURN_NONE;
}

static PyObject *
btree_return_element(zdbcore_BTreeObject *self,
    PyObject *elem, zfs_btree_index_t *index)
{
	if (!index) {
		Py_INCREF(elem);
		return (elem);
	}

	PyObject *tuple = PyTuple_New(2);
	if (!tuple)
		return (NULL);

	PyObject *obj_idx = PyBTreeIndex_FromIndex(&self->tree, index);
	if (!obj_idx) {
		Py_DECREF(tuple);
		return (NULL);
	}

	Py_INCREF(elem);
	PyTuple_SET_ITEM(tuple, 0, elem);
	PyTuple_SET_ITEM(tuple, 1, obj_idx);

	return (tuple);
}

static PyObject *
zdbcore_BTree_find(zdbcore_BTreeObject *self, PyObject *args, PyObject *kwargs)
{
	PyObject *_search = NULL, *return_index = NULL;

	char *kwlist[] = { "element", "return_where", NULL };
	if (!PyArg_ParseTupleAndKeywords(
	    args, kwargs, "O|O", kwlist, &_search, &return_index))
		return (NULL);

	if (!PyObject_TypeCheck(_search, self->type)) {
		PyErr_Format(PyExc_TypeError,
		    "Expected type '%s' but received type '%s'",
		    self->type->tp_name, Py_TYPE(_search)->tp_name);
		return (NULL);
	}

	zfs_btree_index_t _index, *index = NULL;
	if (return_index && PyObject_IsTrue(return_index)) {
		index = &_index;
		memset(index, 0, sizeof(*index));
	}

	BTreeNode search = { .obj = _search };
	BTreeNode *n = zfs_btree_find(&self->tree, &search, index);
	return (btree_return_element(self, n ? n->obj : Py_None, index));
}

static PyObject *
btree_return_first_or_last(zdbcore_BTreeObject *self,
    PyObject *args, PyObject *kwargs, boolean_t return_first)
{
	PyObject *return_index = NULL;

	char *kwlist[] = { "return_where", NULL };
	if (!PyArg_ParseTupleAndKeywords(
	    args, kwargs, "|O", kwlist, &return_index))
		return (NULL);

	zfs_btree_index_t _index, *index = NULL;
	if (return_index && PyObject_IsTrue(return_index)) {
		index = &_index;
		memset(index, 0, sizeof(*index));
	}

	BTreeNode *n = return_first ?
	    zfs_btree_first(&self->tree, index) :
	    zfs_btree_last(&self->tree, index);
	return (btree_return_element(self, n ? n->obj : Py_None, index));
}

enum {
	GET_PREV,
	GET_CURR,
	GET_NEXT,
};

static PyObject *
btree_get_value(zdbcore_BTreeObject *self, PyObject *args, int which)
{
	PyObject *_where = NULL;
	if (!PyArg_ParseTuple(args, "O", &_where))
		return (NULL);

	if (!PyObject_TypeCheck(_where, &zdbcore_BTreeIndexType)) {
		PyErr_Format(PyExc_TypeError, "Expected type '%s' but not '%s'",
		    zdbcore_BTreeIndexType.tp_name,
		    Py_TYPE(_where)->tp_name);
		return (NULL);
	}

	zdbcore_BTreeIndexObject *where = (zdbcore_BTreeIndexObject*)_where;
	BTreeNode *n;
	switch (which) {
	case GET_NEXT:
		n = zfs_btree_next(&self->tree, &where->index, &where->index);
		break;

	case GET_PREV:
		n = zfs_btree_prev(&self->tree, &where->index, &where->index);
		break;

	case GET_CURR:
	default:
		n = zfs_btree_get(&self->tree, &where->index);
		break;
	}

	if (n) {
		Py_INCREF(n->obj);
		return (n->obj);
	} else {
		Py_RETURN_NONE;
	}
}

static PyObject *
zdbcore_BTree_first(zdbcore_BTreeObject *self, PyObject *args, PyObject *kwargs)
{
	return (btree_return_first_or_last(self,
	    args, kwargs, /*return_first=*/1));
}

static PyObject *
zdbcore_BTree_last(zdbcore_BTreeObject *self, PyObject *args, PyObject *kwargs)
{
	return (btree_return_first_or_last(self,
	    args, kwargs, /*return_first=*/0));
}

static PyObject *
zdbcore_BTree_curr(zdbcore_BTreeObject *self, PyObject *args)
{
	return (btree_get_value(self, args, GET_CURR));
}

static PyObject *
zdbcore_BTree_next(zdbcore_BTreeObject *self, PyObject *args)
{
	return (btree_get_value(self, args, GET_NEXT));
}

static PyObject *
zdbcore_BTree_prev(zdbcore_BTreeObject *self, PyObject *args)
{
	return (btree_get_value(self, args, GET_PREV));
}

static unsigned long
btree_size(PyObject *_self)
{
	zdbcore_BTreeObject *self = (zdbcore_BTreeObject*)_self;
	return (zfs_btree_numnodes(&self->tree));
}

static PyObject *
zdbcore_BTree_size(PyObject *self, void *closure)
{
	return (PY_INT_FROM(btree_size(self)));
}

static PyGetSetDef zdbcore_BTree_getseters[] = {
	PROPERTY_RDONLY(
	    "size",
	    "number of btree's nodes",
	    zdbcore_BTree_size),
	PROPERTY_NULL
};

static Py_ssize_t
zdbcore_BTree_len(PyObject *self)
{
	return ((Py_ssize_t)btree_size(self));
}

static PySequenceMethods zdbcore_BTree_as_sequence = {
	.sq_length = zdbcore_BTree_len,
};

static PyMethodDef zdbcore_BTree_methods[] = {
	{
		"add",
		(PyCFunction)zdbcore_BTree_add,
		METH_VARARGS,
		"add(element[,where]) -> None"
	}, {
		"remove",
		(PyCFunction)zdbcore_BTree_remove,
		METH_VARARGS,
		"remove(element or where) -> None"
	}, {
		"clear",
		(PyCFunction)zdbcore_BTree_clear,
		METH_NOARGS,
		"clear() -> None"
	}, {
		"find",
		(PyCFunction)zdbcore_BTree_find,
		METH_VARARGS,
		"find(search[,return_where=False]) -> element[,where]"
	}, {
		"first",
		(PyCFunction)zdbcore_BTree_first,
		METH_VARARGS,
		"first([return_where=False]) -> element[,where]"
	}, {
		"last",
		(PyCFunction)zdbcore_BTree_last,
		METH_VARARGS,
		"last([return_where=False]) -> element[,where]"
	}, {
		"get",
		(PyCFunction)zdbcore_BTree_curr,
		METH_VARARGS,
		"get(where) -> element"
	}, {
		"next",
		(PyCFunction)zdbcore_BTree_next,
		METH_VARARGS,
		"next(where) -> element"
	}, {
		"prev",
		(PyCFunction)zdbcore_BTree_prev,
		METH_VARARGS,
		"prev(where) -> element"
	}, {NULL}
};

PyTypeObject zdbcore_BTreeType = {
	PyVarObject_HEAD_INIT(NULL, 0)
	.tp_name = "core.BTree",
	.tp_doc = "BTree Object",
	.tp_basicsize = sizeof(zdbcore_BTreeObject),
	.tp_flags = Py_TPFLAGS_DEFAULT | Py_TPFLAGS_BASETYPE,
	.tp_init = (initproc)zdbcore_BTree_init,
	.tp_new = zdbcore_BTree_new,
	.tp_dealloc = (destructor)zdbcore_BTree_dealloc,
	.tp_methods = zdbcore_BTree_methods,
	.tp_getset = zdbcore_BTree_getseters,
	.tp_as_sequence = &zdbcore_BTree_as_sequence,
};

void
zdbcore_btree_init(void)
{
	zfs_btree_init();
}

void
zdbcore_btree_fini(void)
{
	zfs_btree_fini();
}
