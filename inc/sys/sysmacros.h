#ifndef __SPL_SYS_SYSMACROS_H
#define __SPL_SYS_SYSMACROS_H

#include_next <sys/sysmacros.h>

#define MAX(x,y) ((x) >= (y) ? (x) : (y))
#define MIN(x,y) ((x) <= (y) ? (x) : (y))

#endif // __SPL_SYS_SYSMACROS_H
