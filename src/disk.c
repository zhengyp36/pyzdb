#include <stdio.h>
#include <errno.h>
#include <fcntl.h>
#include <unistd.h>
#include <limits.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/mman.h>
#include <sys/ioctl.h>
#include <linux/fs.h>
#include <zdb/comm.h>
#include <zdb/disk.h>

void
disk_init(disk_t *disk)
{
	memset(disk, 0, sizeof(*disk));
}

static int disk_is_readonly = 1;

int
disk_open(disk_t *disk, const char *path, char **err)
{
	char errinfo[1024];
	int fd = -1, ret = -1;

#define LogErr(fmt,...) snprintf(errinfo, sizeof(errinfo), fmt, ##__VA_ARGS__)

	do {
		long pagesize;
		*err = NULL;
		errinfo[0] = '\0';

		disk->path = realpath(path, NULL);
		if (!disk->path) {
			LogErr("Failed to locate path '%s'", path);
			break;
		}

		disk->readonly = disk_is_readonly;
		fd = open(disk->path, O_RDONLY);
		if (fd < 0) {
			LogErr("Failed to open disk %s, errno %d",
			    disk->path, errno);
			break;
		}

		if (ioctl(fd, BLKSSZGET, &disk->sector_size)) {
			LogErr("Failed to get sector size of '%s'", disk->path);
			break;
		}

		if (ioctl(fd, BLKGETSIZE64, &disk->capacity)) {
			LogErr("Failed to get capacity of '%s'", disk->path);
			break;
		}

		pagesize = sysconf(_SC_PAGESIZE);
		disk->map_size = (disk->capacity + pagesize - 1) & -pagesize;
		if (disk->readonly)
			disk->addr = mmap(NULL, disk->map_size,
			    PROT_READ, MAP_PRIVATE, fd, 0);
		else
			disk->addr = mmap(NULL, disk->map_size,
			    PROT_READ | PROT_WRITE, MAP_SHARED, fd, 0);
		if (disk->addr == MAP_FAILED) {
			disk->addr = NULL;
			LogErr("Failed to mmap %s with size %lu, errno %d",
			    disk->path, disk->map_size, errno);
			break;
		}

		BUILD_BUG_ON(sizeof(disk->size) != sizeof(disk->capacity));

		ret = 0;
	} while (0);

	if (fd >= 0)
		close(fd);
	if (ret) {
		*err = strdup(errinfo);
		disk_close(disk);
	}

	return (ret);
}

void
disk_err_free(char **err)
{
	if (err && *err) {
		free(*err);
		*err = NULL;
	}
}

void
disk_close(disk_t *disk)
{
	if (disk->path) {
		free(disk->path);
		disk->path = NULL;
	}

	if (disk->addr) {
		munmap(disk->addr, disk->map_size);
		disk->addr = NULL;
	}
}
