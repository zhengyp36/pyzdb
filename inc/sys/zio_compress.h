#ifndef __SYS_ZFS_COMPRESS_H
#define __SYS_ZFS_COMPRESS_H

enum zio_compress_type {
	ZIO_COMPRESS_INHERIT = 0, /*  0 */  /* Not supported */
	ZIO_COMPRESS_ON,          /*  1 */  /* Not supported */
	ZIO_COMPRESS_OFF,         /*  2 */  /* Not supported */
	ZIO_COMPRESS_LZJB,        /*  3 */
	ZIO_COMPRESS_EMPTY,       /*  4 */  /* Not supported */
	ZIO_COMPRESS_GZIP_1,      /*  5 */
	ZIO_COMPRESS_GZIP_2,      /*  6 */
	ZIO_COMPRESS_GZIP_3,      /*  7 */
	ZIO_COMPRESS_GZIP_4,      /*  8 */
	ZIO_COMPRESS_GZIP_5,      /*  9 */
	ZIO_COMPRESS_GZIP_6,      /* 10 */
	ZIO_COMPRESS_GZIP_7,      /* 11 */
	ZIO_COMPRESS_GZIP_8,      /* 12 */
	ZIO_COMPRESS_GZIP_9,      /* 13 */
	ZIO_COMPRESS_ZLE,         /* 14 */
	ZIO_COMPRESS_LZ4,         /* 15 */
	ZIO_COMPRESS_ZSTD,        /* 16 */  /* Not supported */
	ZIO_COMPRESS_FUNCTIONS    /* 17 */
};

void zio_compress_init(void);
void zio_compress_fini(void);

/*
 * Failed to compress if return size >= slen
 */
size_t zio_compress(enum zio_compress_type compress_type,
    void *src, void *dst, size_t slen, size_t dlen);

/*
 * Return 0 if success
 */
int zio_decompress(enum zio_compress_type compress_type,
    void *src, void *dst, size_t slen, size_t dlen);

/* Common signature for all zio compress functions. */
typedef size_t zio_compress_func_t(void *src, void *dst,
    size_t s_len, size_t d_len, int);
/* Common signature for all zio decompress functions. */
typedef int zio_decompress_func_t(void *src, void *dst,
    size_t s_len, size_t d_len, int);
/* Common signature for all zio decompress and get level functions. */
typedef int zio_decompresslevel_func_t(void *src, void *dst,
    size_t s_len, size_t d_len, uint8_t *level);

typedef const struct zio_compress_info {
	const char			*ci_name;
	int				ci_level;
	zio_compress_func_t		*ci_compress;
	zio_decompress_func_t		*ci_decompress;
	zio_decompresslevel_func_t	*ci_decompress_level;
} zio_compress_info_t;

/* lzjb */
size_t lzjb_compress(void *src, void *dst, size_t slen, size_t dlen, int _);
int lzjb_decompress(void *src, void *dst, size_t slen, size_t dlen, int _);

/* gzip */
size_t gzip_compress(void *src, void *dst, size_t slen, size_t dlen, int _);
int gzip_decompress(void *src, void *dst, size_t slen, size_t dlen, int _);

/* zle */
size_t zle_compress(void *src, void *dst, size_t slen, size_t dlen, int _);
int zle_decompress(void *src, void *dst, size_t slen, size_t dlen, int _);

/* lz4 */
void lz4_init(void);
void lz4_fini(void);
size_t lz4_compress_zfs(void *src, void *dst, size_t slen, size_t dlen, int level);
int lz4_decompress_zfs(void *src, void *dst, size_t slen, size_t dlen, int level);

/* zstd */
// TODO: It's too complex to be imported

#endif // __SYS_ZFS_COMPRESS_H
