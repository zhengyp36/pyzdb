#ifndef __SYS_ZFS_CONTEXT_H
#define __SYS_ZFS_CONTEXT_H

#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <sys/debug.h>
#include <sys/types.h>
#include <sys/sysmacros.h>
#include <sys/kmem_adapter.h>
#include <zdb/comm.h>

#ifndef NBBY
#define NBBY 8
#else
static inline void __compile_check_NBBY(void) { BUILD_BUG_ON(NBBY != 8); }
#endif

#define	BE_IN8(xa) \
	*((uint8_t *)(xa))

#define	BE_IN16(xa) \
	(((uint16_t)BE_IN8(xa) << 8) | BE_IN8((uint8_t *)(xa)+1))

#define	BE_IN32(xa) \
	(((uint32_t)BE_IN16(xa) << 16) | BE_IN16((uint8_t *)(xa)+2))

#define	BE_32(x)	BSWAP_32(x)
#define	BSWAP_8(x)	((x) & 0xff)
#define	BSWAP_16(x)	((BSWAP_8(x) << 8) | BSWAP_8((x) >> 8))
#define	BSWAP_32(x)	((BSWAP_16(x) << 16) | BSWAP_16((x) >> 16))

#define	ZFS_MODULE_PARAM(scope_prefix, name_prefix, name, type, perm, desc)

#endif // __SYS_ZFS_CONTEXT_H
