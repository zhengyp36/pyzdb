/*
 * Some definitions in this file are derived from OpenZFS source code.
 * OpenZFS is licensed under the Common Development and Distribution
 * License (CDDL). See https://github.com/openzfs/zfs
 */

#ifndef __SYS_DEBUG_H
#define __SYS_DEBUG_H

#include <string.h> /* gzip.c needs memcpy */
#include <assert.h>

#ifndef assert
#define assert assert
#endif

#ifdef NDEBUG
#define verify(cond) do { if (!(cond)) *(int*)0 = 0; } while (0)
#else
#define verify(cond) assert(cond)
#endif

#ifndef ASSERT
#define ASSERT(cond) assert(cond)
#define ASSERT0(cond) assert(!(cond))
#define ASSERT3U(x,op,y) ASSERT((uintptr_t)(x) op (uintptr_t)(y))
#define ASSERT3S(x,op,y) ASSERT((intptr_t)(x) op (intptr_t)(y))
#define ASSERT3P(x,op,y) ASSERT((uintptr_t)(x) op (uintptr_t)(y))
#endif

#ifndef VERIFY
#define VERIFY(cond) verify(cond)
#define VERIFY0(cond) VERIFY(!(cond))
#define VERIFY3U(x,op,y) VERIFY((uintptr_t)(x) op (uintptr_t)(y))
#define VERIFY3S(x,op,y) VERIFY((intptr_t)(x) op (intptr_t)(y))
#define VERIFY3P(x,op,y) VERIFY((uintptr_t)(x) op (uintptr_t)(y))
#endif

#ifndef EQUIV
#define EQUIV(A,B) VERIFY(!!(A) == !!(B))
#endif

#define panic(fmt...) verify(0)

#endif // __SYS_DEBUG_H
