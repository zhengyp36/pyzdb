/*
 * Some definitions in this file are derived from OpenZFS source code.
 * OpenZFS is licensed under the Common Development and Distribution
 * License (CDDL). See https://github.com/openzfs/zfs
 */

#ifndef __SPL_SYS_TYPES_H
#define __SPL_SYS_TYPES_H

#include <stdint.h>
#include_next <sys/types.h>

typedef enum {
	B_FALSE = 0,
	B_TRUE = 1
} boolean_t;

typedef unsigned char		uchar_t;
typedef unsigned short		ushort_t;
typedef unsigned int		uint_t;
typedef unsigned long		ulong_t;
typedef unsigned long long	u_longlong_t;
typedef long long		longlong_t;

#endif // __SPL_SYS_TYPES_H
