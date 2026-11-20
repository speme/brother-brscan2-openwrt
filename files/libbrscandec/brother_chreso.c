/*
 * Architecture-neutral pass-through implementation of Brother's ChangeReso
 * entry points. brscan2 passes a fixed 64-bit ABI block to these functions.
 * This backend leaves line scaling disabled and copies decoded lines as-is;
 * the scanner firmware must deliver the requested resolution.
 *
 * This is intended for monochrome Brother devices such as MFC-7420. It is not
 * a replacement for Brother's resampling algorithms.
 */
#include <stdint.h>
#include <stddef.h>
#include <limits.h>
#include <string.h>

#include "brother_scandec.h"

ulong ChangeResoInit(undefined8 *opaque)
{
	uint64_t *args = (uint64_t *)opaque;
	uint64_t pixels = args[3];
	uint32_t color_type = (uint32_t)args[2];
	uint64_t bytes_per_pixel = ((color_type >> 10) & 1) ? 3 : 1;
	uint64_t line_bytes = pixels * bytes_per_pixel;

	args[5] = pixels;
	args[6] = line_bytes;
	args[7] = line_bytes;
	return 1;
}

undefined8 ChangeResoClose(void)
{
	return 1;
}

long ChangeResoWrite(void *opaque, undefined4 *lines_written)
{
	uint64_t *args = (uint64_t *)opaque;
	const uint8_t *src = (const uint8_t *)(uintptr_t)args[1];
	uint64_t size = args[2];
	uint8_t *dst = (uint8_t *)(uintptr_t)args[3];
	uint64_t capacity = args[4];

	*lines_written = 0;
	if (!src || !dst || size > capacity || size > LONG_MAX)
		return 0;
	memcpy(dst, src, (size_t)size);
	*lines_written = 1;
	return (long)size;
}

ulong ChangeResoWriteStart(void)
{
	return 1;
}

long ChangeResoWriteEnd(void *opaque, undefined4 *lines_written)
{
	(void)opaque;
	*lines_written = 0;
	return 0;
}
