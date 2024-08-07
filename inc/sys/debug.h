#ifndef __SYS_DEBUG_H
#define __SYS_DEBUG_H

#include <string.h> /* gzip.c needs memcpy */
#include <assert.h>

#ifndef assert
#define assert assert
#endif

#ifndef ASSERT
#define ASSERT(cond) assert(cond)
#endif

#endif // __SYS_DEBUG_H
