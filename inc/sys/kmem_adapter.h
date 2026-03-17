/*
 * Some definitions in this file are derived from OpenZFS source code.
 * OpenZFS is licensed under the Common Development and Distribution
 * License (CDDL). See https://github.com/openzfs/zfs
 */

#ifndef __SYS_KMEM_ADAPTER_H
#define __SYS_KMEM_ADAPTER_H

#include <stdlib.h>

#define KM_SLEEP 0
#define kmem_alloc(size,flag) malloc(size)
#define kmem_zalloc(size,flag) calloc(1,size)
#define kmem_free(ptr,size) free(ptr)

typedef struct {
	size_t elem_size;
} kmem_cache_t;

static inline kmem_cache_t *
kmem_cache_create(const char *name, size_t size,
    int flag, void *_1, void *_2, void *_3, void *_4, void *_5, int _6)
{
	kmem_cache_t *kc = malloc(sizeof(kmem_cache_t));
	if (kc)
		kc->elem_size = size;
	return (kc);
}

static inline void *
kmem_cache_alloc(kmem_cache_t *kc, int flag)
{
	return (malloc(kc->elem_size));
}

static inline void
kmem_cache_free(kmem_cache_t *kc, void *elem)
{
	if (elem)
		free(elem);
}

static inline void
kmem_cache_destroy(kmem_cache_t *kc)
{
	if (kc)
		free(kc);
}

#endif // __SYS_KMEM_ADAPTER_H
