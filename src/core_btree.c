#include "internal.h"
#include <sys/btree.h>

typedef struct {
	const zfs_btree_t *	tree;
	zfs_btree_index_t	index;
} btree_index_t;

typedef struct {
	PyObject *		obj;
} btree_node_t;

typedef struct {
	zfs_btree_t		tree;
	PyTypeObject *		elem_type;
	PyObject *		elem_cmp;
	int			cmp_error;
	int			inited;
} btree_t;

typedef struct {
	PyObject_HEAD
	btree_index_t bti;
} BTreeIndex;

typedef struct {
	PyObject_HEAD
	btree_t bt;
} BTree;

static PyObject *
BTreeIndex_new(PyTypeObject *type, PyObject *args, PyObject *kwargs)
{
	BTreeIndex *self = (BTreeIndex*)type->tp_alloc(type, 0);
	if (self)
		memset(&self->bti, 0, sizeof(self->bti));
	return ((PyObject*)self);
}

static int
BTreeIndex_init(BTreeIndex *self, PyObject *args, PyObject *kwargs)
{
	return (0);
}

static void
BTreeIndex_dealloc(BTreeIndex *self)
{
	Py_TYPE(self)->tp_free((PyObject*)self);
}

static PyObject *
BTreeIndex_copy(BTreeIndex *self, PyObject *noargs)
{
	BTreeIndex *other = PyObject_New(BTreeIndex, Py_TYPE(self));
	if (other)
		other->bti = self->bti;
	return ((PyObject*)other);
}

static PyMethodDef BTreeIndex_methods[] = {
	{
		"copy",
		(PyCFunction)BTreeIndex_copy,
		METH_NOARGS,
		"copy() -> A copy of the object"
	}, {NULL}
};

PyTypeObject zdbcore_BTreeIndexType = {
	PyVarObject_HEAD_INIT(NULL, 0)
	.tp_name = "core.BTreeIndex",
	.tp_doc = "BTreeIndex Object",
	.tp_basicsize = sizeof(BTreeIndex),
	.tp_flags = Py_TPFLAGS_DEFAULT | Py_TPFLAGS_BASETYPE,
	.tp_new = BTreeIndex_new,
	.tp_init = (initproc)BTreeIndex_init,
	.tp_dealloc = (destructor)BTreeIndex_dealloc,
	.tp_methods = BTreeIndex_methods,
};

PyObject *
PyBTreeIndex_FromIndex(const zfs_btree_t *tree, const zfs_btree_index_t *index)
{
	if (index->bti_node == NULL)
		Py_RETURN_NONE;

	BTreeIndex *self = PyObject_New(BTreeIndex, &zdbcore_BTreeIndexType);
	if (self) {
		self->bti.tree = tree;
		self->bti.index = *index;
	}

	return ((PyObject*)self);
}

static inline long
py_long_as(PyObject *result)
{
#ifdef IS_PY3K // Python-3.x
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

static int
btree_node_cmp(const void *_n1, const void *_n2, void *arg)
{
	btree_t *bt = (btree_t*)arg;
	const btree_node_t *n1 = (const btree_node_t*)_n1;
	const btree_node_t *n2 = (const btree_node_t*)_n2;

	PyObject *result = PyObject_CallFunctionObjArgs(bt->elem_cmp,
	    n1->obj, n2->obj, NULL);
	if (result) {
		long cmp_result = py_long_as(result);
		if (!PyErr_Occurred())
			return ((int)cmp_result);
	}

	bt->cmp_error = -1;
	/* return 0 to stop traverse the btree */
	return (0);
}

static void
btree_init(btree_t *bt, PyTypeObject *elem_type, PyObject *elem_cmp)
{
	Py_INCREF(elem_cmp);
	Py_INCREF((PyObject*)elem_type);
	bt->elem_cmp = elem_cmp;
	bt->elem_type = elem_type;

	zfs_btree_create(&bt->tree, btree_node_cmp, bt, sizeof(btree_node_t));

	bt->cmp_error = 0;
	bt->inited = 1;
}

static void
btree_add(btree_t *bt, PyObject *elem, const btree_index_t *bti)
{
	btree_node_t n = { .obj = elem };
	Py_INCREF(elem);

	if (bti)
		zfs_btree_add_idx(&bt->tree, &n, &bti->index);
	else
		zfs_btree_add(&bt->tree, &n);
}

static void
btree_clear(btree_t *bt)
{
	btree_node_t *n;
	zfs_btree_index_t *cookie = NULL;
	while ((n = zfs_btree_destroy_nodes(&bt->tree, &cookie)))
		Py_DECREF(n->obj);
}

static void
btree_destroy(btree_t *bt)
{
	if (bt->inited) {
		btree_clear(bt);
		zfs_btree_destroy(&bt->tree);

		Py_DECREF(bt->elem_cmp);
		Py_DECREF((PyObject*)bt->elem_type);
		bt->elem_cmp = NULL;
		bt->elem_type = NULL;

		bt->inited = 0;
	}
}

static PyObject *
BTree_new(PyTypeObject *type, PyObject *args, PyObject *kwargs)
{
	BTree *self = (BTree*)type->tp_alloc(type, 0);
	if (self)
		memset(&self->bt, 0, sizeof(self->bt));
	return ((PyObject*)self);
}

static int
BTree_init(BTree *self, PyObject *args, PyObject *kwargs)
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

	btree_init(&self->bt, (PyTypeObject*)type, cmp);
	return (0);
}

static void
BTree_dealloc(BTree *self)
{
	btree_destroy(&self->bt);
	Py_TYPE(self)->tp_free((PyObject*)self);
}

static inline boolean_t
is_elem_type(btree_t *bt, PyObject *elem)
{
	return (!!PyObject_TypeCheck(elem, bt->elem_type));
}

static inline int
btree_check_elem(btree_t *bt, PyObject *elem)
{
	if (is_elem_type(bt, elem)) {
		return (0);
	} else {
		PyErr_Format(PyExc_TypeError,
		    "Expected type '%s' but received type '%s'",
		    bt->elem_type->tp_name, Py_TYPE(elem)->tp_name);
		return (-1);
	}
}

static inline boolean_t
is_index_type(PyObject *where)
{
	return (!!PyObject_TypeCheck(where, &zdbcore_BTreeIndexType));
}

static inline int
btree_check_index(btree_t *bt, PyObject *where)
{
	if (!is_index_type(where)) {
		PyErr_Format(PyExc_TypeError,
		    "Expected type '%s' but received type '%s'",
		    zdbcore_BTreeIndexType.tp_name, Py_TYPE(where)->tp_name);
		return (-1);
	}

	BTreeIndex *index = (BTreeIndex*)where;
	if (index->bti.tree != &bt->tree) {
		PyErr_SetString(PyExc_ValueError,
		    "The argument 'where' does not belong to this tree.");
		return (-1);
	}

	return (0);
}

static PyObject *
BTree_add(BTree *self, PyObject *args, PyObject *kwargs)
{
	PyObject *elem = NULL, *where = NULL;
	char *kwlist[] = { "element", "where", NULL };
	if (!PyArg_ParseTupleAndKeywords(
	    args, kwargs, "O|O", kwlist, &elem, &where))
		return (NULL);

	if (btree_check_elem(&self->bt, elem) ||
	    (where && btree_check_index(&self->bt, where)))
		return (NULL);

	BTreeIndex *index = (BTreeIndex*)where;
	btree_add(&self->bt, elem, index ? &index->bti : NULL);
	Py_RETURN_NONE;
}

static PyObject *
BTree_remove(BTree *self, PyObject *args, PyObject *kwargs)
{
	PyObject *elem = NULL, *where = NULL;
	char *kwlist[] = { "element", "where", NULL };
	if (!PyArg_ParseTupleAndKeywords(
	    args, kwargs, "|OO", kwlist, &elem, &where))
		return (NULL);

	if (!elem && !where) {
		PyObject *arg;
		if (!PyArg_ParseTuple(args, "O", &arg))
			return (NULL);

		if (is_elem_type(&self->bt, arg)) {
			elem = arg;
		} else if (is_index_type(arg)) {
			where = arg;
		} else {
			PyErr_Format(PyExc_TypeError,
			    "Expected type '%s' or '%s' but not '%s'",
			    self->bt.elem_type->tp_name,
			    zdbcore_BTreeIndexType.tp_name,
			    Py_TYPE(arg)->tp_name);
			return (NULL);
		}
	}

	if (elem && where) {
		PyErr_Format(PyExc_ValueError,
		    "It's wrong that element and where are both given.");
		return (NULL);
	}

	if ((elem && btree_check_elem(&self->bt, elem)) ||
	    (where && btree_check_index(&self->bt, where)))
		return (NULL);

	if (elem) {
		btree_node_t n = { .obj = elem };
		zfs_btree_remove(&self->bt.tree, &n);
	} else {
		zfs_btree_index_t *index = &((BTreeIndex*)where)->bti.index;
		zfs_btree_remove_idx(&self->bt.tree, index);
	}

	Py_RETURN_NONE;
}

static PyObject *
BTree_clear(BTree *self, PyObject *noargs)
{
	btree_clear(&self->bt);
	Py_RETURN_NONE;
}

static PyObject *
btree_return_element(btree_t *bt, PyObject *elem, zfs_btree_index_t *index)
{
	if (!index) {
		Py_INCREF(elem);
		return (elem);
	}

	PyObject *tuple = PyTuple_New(2);
	if (!tuple)
		return (NULL);

	PyObject *obj_idx = PyBTreeIndex_FromIndex(&bt->tree, index);
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
BTree_find(BTree *self, PyObject *args, PyObject *kwargs)
{
	PyObject *_search = NULL, *return_index = NULL;

	char *kwlist[] = { "element", "return_where", NULL };
	if (!PyArg_ParseTupleAndKeywords(
	    args, kwargs, "O|O", kwlist, &_search, &return_index))
		return (NULL);

	if (btree_check_elem(&self->bt, _search))
		return (NULL);

	zfs_btree_index_t _index, *index = NULL;
	if (return_index && PyObject_IsTrue(return_index)) {
		index = &_index;
		memset(index, 0, sizeof(*index));
	}

	btree_node_t search = { .obj = _search };
	btree_node_t *n = zfs_btree_find(&self->bt.tree, &search, index);
	return (btree_return_element(&self->bt, n ? n->obj : Py_None, index));
}

enum {
	GET_FIRST,
	GET_LAST,

	GET_PREV,
	GET_CURR,
	GET_NEXT,
};

static PyObject *
btree_return_first_or_last(btree_t *bt,
    PyObject *args, PyObject *kwargs, int which)
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

	btree_node_t *n = (which == GET_FIRST) ?
	    zfs_btree_first(&bt->tree, index) :
	    zfs_btree_last(&bt->tree, index);
	return (btree_return_element(bt, n ? n->obj : Py_None, index));
}

static PyObject *
btree_get_value(btree_t *bt, PyObject *args, int which)
{
	PyObject *where = NULL;
	if (!PyArg_ParseTuple(args, "O", &where))
		return (NULL);

	if (btree_check_index(bt, where))
		return (NULL);

	zfs_btree_index_t *index = &((BTreeIndex*)where)->bti.index;
	btree_node_t *n;

	switch (which) {
	case GET_NEXT:
		n = zfs_btree_next(&bt->tree, index, index);
		break;

	case GET_PREV:
		n = zfs_btree_prev(&bt->tree, index, index);
		break;

	case GET_CURR:
	default:
		n = zfs_btree_get(&bt->tree, index);
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
BTree_first(BTree *self, PyObject *args, PyObject *kwargs)
{
	return (btree_return_first_or_last(&self->bt, args, kwargs, GET_FIRST));
}

static PyObject *
BTree_last(BTree *self, PyObject *args, PyObject *kwargs)
{
	return (btree_return_first_or_last(&self->bt, args, kwargs, GET_LAST));
}

static PyObject *
BTree_curr(BTree *self, PyObject *args)
{
	return (btree_get_value(&self->bt, args, GET_CURR));
}

static PyObject *
BTree_next(BTree *self, PyObject *args)
{
	return (btree_get_value(&self->bt, args, GET_NEXT));
}

static PyObject *
BTree_prev(BTree *self, PyObject *args)
{
	return (btree_get_value(&self->bt, args, GET_PREV));
}

static unsigned long
btree_size(PyObject *_self)
{
	BTree *self = (BTree*)_self;
	return (zfs_btree_numnodes(&self->bt.tree));
}

static inline PyObject *
get_method(PyObject *obj, const char *name)
{
	PyObject *method = PyObject_GetAttrString(obj, name);
	if (method && PyCallable_Check(method)) {
		return (method);
	} else {
		Py_XDECREF(method);
		return (NULL);
	}
}

#define call_method(method, ...) \
	PyObject_CallFunctionObjArgs(method, ##__VA_ARGS__, NULL)

static void
pop_objs(PyObject *list, int cnt)
{
	PyObject *pop = get_method(list, "pop");
	if (!pop)
		return;

	while (cnt-- > 0) {
		PyObject *obj = call_method(pop);
		if (obj)
			Py_DECREF(obj);
	}

	Py_DECREF(pop);
}

static int
append_objs(PyObject *list, zfs_btree_t *tree)
{
	PyObject *append = get_method(list, "append");
	if (!append)
		return (-1);

	btree_node_t *n;
	zfs_btree_index_t idx;
	int cnt = 0, err = 0;

	for (n = zfs_btree_first(tree, &idx); n;
	    n = zfs_btree_next(tree, &idx, &idx)) {
		PyObject *r = call_method(append, n->obj);
		if (r) {
			Py_DECREF(r);
			Py_INCREF(n->obj);
			cnt++;
		} else {
			err = -1;
			break;
		}
	}
	Py_DECREF(append);

	if (!err)
		return (0);

	if (cnt > 0)
		pop_objs(list, cnt);

	return (-1);
}

static PyObject *
BTree_tolist(BTree *self, PyObject *noargs)
{
	PyObject *list = PyList_New(0);
	if (!list)
		return (NULL);

	if (append_objs(list, &self->bt.tree)) {
		Py_DECREF(list);
		return (NULL);
	}

	return (list);
}

static PyObject *
BTree_size(PyObject *self, void *closure)
{
	return (PY_INT_FROM(btree_size(self)));
}

static PyGetSetDef BTree_getseters[] = {
	PROPERTY_RDONLY(
	    "size",
	    "number of btree's nodes",
	    BTree_size),
	PROPERTY_NULL
};

static PyMethodDef BTree_methods[] = {
	{
		"_add",
		(PyCFunction)BTree_add,
		METH_VARARGS | METH_KEYWORDS,
		"add(element[,where]) -> None"
	}, {
		"_remove",
		(PyCFunction)BTree_remove,
		METH_VARARGS | METH_KEYWORDS,
		"remove(element or where) -> None"
	}, {
		"_clear",
		(PyCFunction)BTree_clear,
		METH_NOARGS | METH_KEYWORDS,
		"clear() -> None"
	}, {
		"_find",
		(PyCFunction)BTree_find,
		METH_VARARGS | METH_KEYWORDS,
		"find(search[,return_where=False]) -> element[,where]"
	}, {
		"_first",
		(PyCFunction)BTree_first,
		METH_VARARGS | METH_KEYWORDS,
		"first([return_where=False]) -> element[,where]"
	}, {
		"_last",
		(PyCFunction)BTree_last,
		METH_VARARGS | METH_KEYWORDS,
		"last([return_where=False]) -> element[,where]"
	}, {
		"_get",
		(PyCFunction)BTree_curr,
		METH_VARARGS,
		"get(where) -> element"
	}, {
		"_next",
		(PyCFunction)BTree_next,
		METH_VARARGS,
		"next(where) -> element"
	}, {
		"_prev",
		(PyCFunction)BTree_prev,
		METH_VARARGS,
		"prev(where) -> element"
	}, {
		"_tolist",
		(PyCFunction)BTree_tolist,
		METH_VARARGS,
		"tolist() -> [element,...]"
	}, {NULL}
};

PyTypeObject zdbcore_BTreeType = {
	PyVarObject_HEAD_INIT(NULL, 0)
	.tp_name = "core.CBTree",
	.tp_doc = "BTree Object Implementation",
	.tp_basicsize = sizeof(BTree),
	.tp_flags = Py_TPFLAGS_DEFAULT | Py_TPFLAGS_BASETYPE,
	.tp_init = (initproc)BTree_init,
	.tp_new = BTree_new,
	.tp_dealloc = (destructor)BTree_dealloc,
	.tp_methods = BTree_methods,
	.tp_getset = BTree_getseters,
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
