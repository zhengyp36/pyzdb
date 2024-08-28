#ifndef __SPL_SYS_SYSMACROS_H
#define __SPL_SYS_SYSMACROS_H

#include_next <sys/sysmacros.h>

#define MAX(x,y) ((x) >= (y) ? (x) : (y))
#define MIN(x,y) ((x) <= (y) ? (x) : (y))

#ifndef offsetof
#define offsetof(s,m) ((unsigned long)&((s*)0)->m)
#endif

#ifndef P2PHASE
#define P2PHASE(x,align) ((x) & ((align) - 1))
#endif

#ifndef P2ALIGN
#define P2ALIGN(x, align) ((x) & -(align))
#endif

#endif // __SPL_SYS_SYSMACROS_H
