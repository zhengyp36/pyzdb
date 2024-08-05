#ifndef _ZDB_CORE_DISK_H
#define _ZDB_CORE_DISK_H

typedef struct {
	char *				path;
	void *				addr;
	unsigned int			sector_size;
	unsigned int			readonly;
	union {
		size_t			size;
		unsigned long long	capacity;
	};
	size_t				map_size;
} disk_t;

void disk_init(disk_t *);
int  disk_open(disk_t *, const char *path, char **err);
void disk_err_free(char **err);
void disk_close(disk_t *);

#endif // _ZDB_CORE_DISK_H
