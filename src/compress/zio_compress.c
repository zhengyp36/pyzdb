#include <sys/zfs_context.h>
#include <sys/zio_compress.h>

#define ZIO_ZSTD_LEVEL_DEFAULT 0

static size_t
zfs_zstd_compress_wrap(void *s_start, void *d_start, size_t s_len, size_t d_len,
    int level)
{
	return (s_len);
}

static int
zfs_zstd_decompress(void *s_start, void *d_start, size_t s_len, size_t d_len,
    int level)
{
	return (-1);
}

static int
zfs_zstd_decompress_level(void *s_start, void *d_start, size_t s_len,
    size_t d_len, uint8_t *level)
{
	return (-1);
}

/*
 * Compression vectors.
 */
static zio_compress_info_t zio_compress_table[ZIO_COMPRESS_FUNCTIONS] = {
	{"inherit",	0,	NULL,		NULL, NULL},
	{"on",		0,	NULL,		NULL, NULL},
	{"uncompressed", 0,	NULL,		NULL, NULL},
	{"lzjb",	0,	lzjb_compress,	lzjb_decompress, NULL},
	{"empty",	0,	NULL,		NULL, NULL},
	{"gzip-1",	1,	gzip_compress,	gzip_decompress, NULL},
	{"gzip-2",	2,	gzip_compress,	gzip_decompress, NULL},
	{"gzip-3",	3,	gzip_compress,	gzip_decompress, NULL},
	{"gzip-4",	4,	gzip_compress,	gzip_decompress, NULL},
	{"gzip-5",	5,	gzip_compress,	gzip_decompress, NULL},
	{"gzip-6",	6,	gzip_compress,	gzip_decompress, NULL},
	{"gzip-7",	7,	gzip_compress,	gzip_decompress, NULL},
	{"gzip-8",	8,	gzip_compress,	gzip_decompress, NULL},
	{"gzip-9",	9,	gzip_compress,	gzip_decompress, NULL},
	{"zle",		64,	zle_compress,	zle_decompress, NULL},
	{"lz4",		0,	lz4_compress_zfs, lz4_decompress_zfs, NULL},
	{"zstd",	ZIO_ZSTD_LEVEL_DEFAULT,	zfs_zstd_compress_wrap,
	    zfs_zstd_decompress, zfs_zstd_decompress_level},
};

static int zio_compress_inited = 0;

void
zio_compress_init(void)
{
	lz4_init();
	zio_compress_inited = 1;
}

void
zio_compress_fini(void)
{
	zio_compress_inited = 0;
	lz4_fini();
}

static inline const zio_compress_info_t *
get_comp_info(enum zio_compress_type type)
{
	if (!zio_compress_inited)
		return (NULL);

	if (type < 0 || type >= ZIO_COMPRESS_FUNCTIONS)
		return (NULL);

	const zio_compress_info_t *ci = &zio_compress_table[type];
	if (!ci->ci_compress || !ci->ci_decompress)
		return (NULL);

	return (ci);
}

size_t
zio_compress(enum zio_compress_type type,
    void *src, void *dst, size_t slen, size_t dlen)
{
	const zio_compress_info_t *ci = get_comp_info(type);
	if (ci)
		return (ci->ci_compress(src,dst,slen,dlen,ci->ci_level));
	else
		return (slen); /* Failed to compress */
}

int
zio_decompress(enum zio_compress_type type,
    void *src, void *dst, size_t slen, size_t dlen)
{
	const zio_compress_info_t *ci = get_comp_info(type);
	if (ci)
		return (ci->ci_decompress(src,dst,slen,dlen,ci->ci_level));
	else
		return (-1);
}
