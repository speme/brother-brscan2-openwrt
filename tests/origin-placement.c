#include <assert.h>
#include <stdio.h>
#include <stdint.h>

enum {SANE_STATUS_GOOD=0, SANE_STATUS_INVAL=4,
      SANE_STATUS_EOF=5, SANE_STATUS_IO_ERROR=9};
#include "../files/brother_origin.h"

typedef struct {int width, height, chunk, eof, fail; size_t pos;} Input;
static unsigned char pixel(int y, int x) {return (y * 17 + x) % 251;}
static int raw(void *context, char *out, int capacity, int *length)
{
	Input *s = context;
	size_t total = (size_t)s->width * s->height;
	*length = 0;
	if (s->fail) return SANE_STATUS_IO_ERROR;
	if (s->pos == total) {s->eof++; return SANE_STATUS_EOF;}
	int n = capacity < s->chunk ? capacity : s->chunk;
	if ((size_t)n > total - s->pos) n = total - s->pos;
	for (int i=0;i<n;i++,s->pos++)
		out[i] = pixel(s->pos / s->width, s->pos % s->width);
	*length = n;
	return SANE_STATUS_GOOD;
}

static void exercise(int w, int h, int left, int top, int capacity, int chunk)
{
	BrotherOrigin state;
	Input input = {w,h,chunk,0,0,0};
	brother_origin_reset(&state,w,h,left,top);
	assert(state.enabled);
	unsigned char out[65538];
	size_t emitted = 0;
	for (;;) {
		int n=-1;
		memset(out,0x5a,sizeof(out));
		int rc = brother_origin_read(&state,raw,&input,(char*)out+1,capacity,&n);
		assert(n>=0 && n<=capacity);
		assert(out[0]==0x5a && out[capacity+1]==0x5a);
		for (int i=0;i<n;i++,emitted++) {
			int y=emitted/w, x=emitted%w;
			unsigned char expected=y<top || x<left ? 255 : pixel(y-top,x-left);
			assert(out[i+1]==expected);
		}
		if (rc==SANE_STATUS_EOF) {assert(n==0); break;}
		assert(rc==SANE_STATUS_GOOD && n>0);
	}
	assert(emitted==(size_t)w*h);
	assert(input.pos==(size_t)w*h && input.eof==1);
}

int main(void)
{
	const int sizes[]={1,7,1024,2480,65536};
	for (unsigned i=0;i<sizeof(sizes)/sizeof(*sizes);i++)
		for (int chunk=1;chunk<20;chunk+=8)
			exercise(8,9,2,3,sizes[i],chunk);
	exercise(2480,3506,22,35,1,17);
	exercise(2480,3506,22,35,1024,17);
	exercise(2480,3506,22,35,65536,2480);
	BrotherOrigin state;
	brother_origin_reset(&state,8,9,8,0); assert(!state.enabled);
	brother_origin_reset(&state,8,9,0,9); assert(!state.enabled);
	brother_origin_reset(&state,2481,9,0,0); assert(!state.enabled);
	brother_origin_reset(&state,8,9,2,0);
	Input error={8,9,8,0,1,0}; char out[16]; int n;
	assert(brother_origin_read(&state,raw,&error,out,sizeof(out),&n)==SANE_STATUS_IO_ERROR);
	assert(n==0);
	/* A partial input raster ending at EOF must not masquerade as a row. */
	brother_origin_reset(&state,8,9,2,0);
	Input short_input={7,1,7,0,0,0};
	assert(brother_origin_read(&state,raw,&short_input,out,sizeof(out),&n)==SANE_STATUS_IO_ERROR);
	assert(n==0);
	puts("origin placement: pixel mapping, arbitrary reads, draining, errors passed");
}
