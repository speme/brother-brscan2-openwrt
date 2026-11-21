/*
 * Architecture-neutral implementation of Brother's ChangeReso entry points.
 * brscan2 passes a fixed 64-bit ABI block to these functions. This backend
 * leaves line scaling disabled; the scanner firmware must deliver the
 * requested resolution. Color component lines are assembled into RGB rows.
 *
 * This is not a replacement for Brother's resampling algorithms.
 */
#include <stdint.h>
#include <stddef.h>
#include <limits.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "brother_scandec.h"

/* SCIDK values from Brother's scan-data protocol. */
#define SCIDK_R    2
#define SCIDK_G    3
#define SCIDK_B    4
#define SCIDK_RGB  5
#define SCIDK_BGR  6

static size_t g_pixel_count;
static size_t g_rgb_line_bytes;
static uint8_t *g_rgb_line;
static unsigned g_rgb_line_mask;
static uint8_t g_white_value;
static uint64_t g_gray_rows;
static uint64_t g_gray_short_rows;
static uint64_t g_gray_min_decoded;
static uint64_t g_gray_max_decoded;
static uint64_t g_gray_last_dark_max;

ulong ChangeResoInit(undefined8 *opaque)
{
	uint64_t *args = (uint64_t *)opaque;
	uint64_t pixels = args[3];
	uint32_t color_type = (uint32_t)args[2];
	uint64_t bytes_per_pixel = ((color_type >> 10) & 1) ? 3 : 1;
	if (pixels == 0 || pixels > SIZE_MAX / bytes_per_pixel)
		return 0;
	uint64_t line_bytes = pixels * bytes_per_pixel;

	free(g_rgb_line);
	g_rgb_line = NULL;
	g_pixel_count = (size_t)pixels;
	g_rgb_line_bytes = (size_t)line_bytes;
	g_rgb_line_mask = 0;
	g_white_value = (color_type & (1u << 8)) ? 0 : 255;
	if (bytes_per_pixel == 3) {
		g_rgb_line = malloc(g_rgb_line_bytes);
		if (!g_rgb_line)
			return 0;
	}

	args[5] = pixels;
	args[6] = line_bytes;
	args[7] = line_bytes;
	return 1;
}

undefined8 ChangeResoClose(void)
{
	free(g_rgb_line);
	g_rgb_line = NULL;
	g_pixel_count = 0;
	g_rgb_line_bytes = 0;
	g_rgb_line_mask = 0;
	return 1;
}

long ChangeResoWrite(void *opaque, undefined4 *lines_written)
{
	uint64_t *args = (uint64_t *)opaque;
	const uint8_t *src = (const uint8_t *)(uintptr_t)args[1];
	uint64_t size = args[2];
	uint8_t *dst = (uint8_t *)(uintptr_t)args[3];
	uint64_t capacity = args[4];
	uint32_t kind = (uint32_t)args[0];

	*lines_written = 0;
	if (!src || !dst || size > LONG_MAX)
		return 0;

	/* Monochrome and indexed modes already arrive as one complete line. */
	if (!g_rgb_line) {
		if (size > g_rgb_line_bytes || capacity < g_rgb_line_bytes)
			return 0;
		g_gray_rows++;
		if (size < g_rgb_line_bytes)
			g_gray_short_rows++;
		if (g_gray_rows == 1 || size < g_gray_min_decoded)
			g_gray_min_decoded = size;
		if (size > g_gray_max_decoded)
			g_gray_max_decoded = size;
		for (uint64_t i = size; i > 0; --i) {
			if (src[i - 1] != g_white_value) {
				if (i - 1 > g_gray_last_dark_max)
					g_gray_last_dark_max = i - 1;
				break;
			}
		}
		/* PackBits rows may omit trailing white pixels. The caller counts
		 * a full raster, so return a full raster even for an empty row. */
		memset(dst, g_white_value, g_rgb_line_bytes);
		memcpy(dst, src, (size_t)size);
		*lines_written = 1;
		return (long)g_rgb_line_bytes;
	}

	/* Brother sends either one RGB/BGR pixel line, or three separate
	 * component lines (R, G, B). Assemble the latter before advancing the
	 * output row; treating each component as a complete row splits the image
	 * into three vertical bands in SANE's interleaved RGB frame. */
	if (kind == SCIDK_RGB || kind == SCIDK_BGR) {
		if (size < g_rgb_line_bytes || capacity < g_rgb_line_bytes)
			return 0;
		if (kind == SCIDK_RGB) {
			memcpy(dst, src, g_rgb_line_bytes);
		} else {
			for (size_t i = 0; i < g_pixel_count; ++i) {
				dst[3 * i] = src[3 * i + 2];
				dst[3 * i + 1] = src[3 * i + 1];
				dst[3 * i + 2] = src[3 * i];
			}
		}
		*lines_written = 1;
		return (long)g_rgb_line_bytes;
	}

	if (kind == SCIDK_R || kind == SCIDK_G || kind == SCIDK_B) {
		if (size < g_pixel_count || capacity < g_rgb_line_bytes)
			return 0;
		const unsigned channel = kind - SCIDK_R;
		for (size_t i = 0; i < g_pixel_count; ++i)
			g_rgb_line[3 * i + channel] = src[i];
		g_rgb_line_mask |= 1u << channel;
		if (g_rgb_line_mask != 0x7)
			return 0;

		memcpy(dst, g_rgb_line, g_rgb_line_bytes);
		g_rgb_line_mask = 0;
		*lines_written = 1;
		return (long)g_rgb_line_bytes;
	}

	/* Do not silently pass an unknown color layout through as a valid RGB
	 * image. This backend currently supports only the documented line kinds. */
	return 0;
}

ulong ChangeResoWriteStart(void)
{
	g_rgb_line_mask = 0;
	g_gray_rows = 0;
	g_gray_short_rows = 0;
	g_gray_min_decoded = 0;
	g_gray_max_decoded = 0;
	g_gray_last_dark_max = 0;
	return 1;
}

long ChangeResoWriteEnd(void *opaque, undefined4 *lines_written)
{
	(void)opaque;
	*lines_written = 0;
	if (!g_rgb_line && g_gray_rows != 0)
		fprintf(stderr,
		        "brother2 decoder summary: rows=%llu width=%zu short_rows=%llu decoded_bytes=%llu..%llu last_nonwhite_x=%llu\n",
		        (unsigned long long)g_gray_rows, g_rgb_line_bytes,
		        (unsigned long long)g_gray_short_rows,
		        (unsigned long long)g_gray_min_decoded,
		        (unsigned long long)g_gray_max_decoded,
		        (unsigned long long)g_gray_last_dark_max);
	return 0;
}
