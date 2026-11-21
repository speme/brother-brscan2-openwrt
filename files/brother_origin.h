/* Experimental gray-frame origin placement. Uses one row of storage.
 * The caller supplies SANE_STATUS_* constants and a raw SANE read callback.
 */
#ifndef BROTHER_ORIGIN_H
#define BROTHER_ORIGIN_H
#include <stddef.h>
#include <string.h>

typedef int (*brother_origin_reader)(void *, char *, int, int *);
typedef struct {
	int enabled, width, height, left, top;
	size_t emitted;
	int have, sent, pending;
	unsigned char row[2480];
} BrotherOrigin;

static void brother_origin_reset(BrotherOrigin *s, int width, int height,
				 int left, int top)
{
	memset(s, 0, sizeof(*s));
	s->width = width;
	s->height = height;
	s->left = left;
	s->top = top;
	s->enabled = width > left && left >= 0 && width <= (int)sizeof(s->row)
		&& top >= 0 && height > top;
}

static int brother_origin_read(BrotherOrigin *s, brother_origin_reader read_raw,
			       void *context, char *out, int capacity, int *length)
{
	size_t total = (size_t)s->width * s->height;
	size_t prefix = (size_t)s->width * s->top;
	*length = 0;
	if (!out || capacity <= 0 || !s->enabled)
		return SANE_STATUS_INVAL;
	while (*length < capacity && s->emitted < total) {
		int n = capacity - *length;
		if (s->emitted < prefix) {
			if ((size_t)n > prefix - s->emitted) n = prefix - s->emitted;
			memset(out + *length, 255, n);
		} else {
			while (s->have < s->width) {
				int got = 0, rc;
				if (s->pending != SANE_STATUS_GOOD)
					return *length ? SANE_STATUS_GOOD : s->pending;
				rc = read_raw(context, (char *)s->row + s->have,
					      s->width - s->have, &got);
				if (got < 0 || got > s->width - s->have) {
					s->pending = SANE_STATUS_IO_ERROR;
					return *length ? SANE_STATUS_GOOD : s->pending;
				}
				s->have += got;
				if (rc != SANE_STATUS_GOOD) {
					s->pending = rc;
					if (rc == SANE_STATUS_EOF && s->have != 0 && s->have != s->width)
						s->pending = SANE_STATUS_IO_ERROR;
					if (s->have != s->width || rc != SANE_STATUS_EOF)
						return *length ? SANE_STATUS_GOOD : s->pending;
				}
				if (got == 0 && rc == SANE_STATUS_GOOD) return SANE_STATUS_GOOD;
			}
			if (s->sent == 0) {
				memmove(s->row + s->left, s->row, s->width - s->left);
				memset(s->row, 255, s->left);
			}
			if (n > s->width - s->sent) n = s->width - s->sent;
			memcpy(out + *length, s->row + s->sent, n);
			s->sent += n;
			if (s->sent == s->width) s->have = s->sent = 0;
		}
		*length += n;
		s->emitted += n;
	}
	if (*length) return SANE_STATUS_GOOD;
	/* Consume the displaced bottom rows so raw EOF and device cleanup still
	 * run. Their pixels fall outside the fixed output canvas. */
	while (s->pending == SANE_STATUS_GOOD) {
		int got = 0;
		int rc = read_raw(context, (char *)s->row, sizeof(s->row), &got);
		if (rc != SANE_STATUS_GOOD) s->pending = rc;
		else if (got == 0) return SANE_STATUS_GOOD;
	}
	return s->pending;
}
#endif
