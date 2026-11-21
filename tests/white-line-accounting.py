#!/usr/bin/env python3
"""Test ProcessMain from a prepared (patched) Brother source tree.

Usage: python3 tests/white-line-accounting.py path/to/brother_scanner.c
"""
from pathlib import Path
import os
import subprocess
import sys
import tempfile

source = Path(sys.argv[1]).read_text(errors="replace")
start = source.index("int\nProcessMain(")
body = source.index("{", start)
depth, end = 1, body + 1
while depth:
    if source[end] == "{":
        depth += 1
    elif source[end] == "}":
        depth -= 1
    end += 1

# Stub USB, decoding and color matching; exercise the real packet walker.
status_start = source.index("BOOL\nStatusChk(")
status_end = source.index("\n}", status_start) + 2
prefix = r'''
#include <assert.h>
#include <string.h>
#include <stdint.h>
#include <stdio.h>
typedef unsigned char BYTE,*LPBYTE;
typedef int BOOL;
#define FALSE 0
typedef uint16_t WORD;
typedef uint32_t DWORD;
typedef int32_t LONG;
#define SCAN_GOOD 0
#define SCAN_DUPLEX_NORMAL 2
#define SCAN_DUPLEX_REVERSE 3
#define COLOR_TG 4
#define COLOR_FUL 6
#define COLOR_FUL_NOCM 7
#define WriteLog(...) ((void)0)
static unsigned char *lpRxBuff;
static int lRealY,dwFWImageSize,dwFWImageLine,nWriteLineCount;
static unsigned dwWriteImageSize;
static int force_zero;
static unsigned long scan_packet_rows, scan_white_rows, scan_decode_zero, scan_decoded_rows;
static unsigned scan_last_status;

static struct {
    unsigned char *pLineData,*pWriteBuff;
    unsigned dwLineDataSize;
} ImgLineProcInfo;
static unsigned decode(void *unused,int *lines) {
    (void)unused;
    if (force_zero) { *lines=0; return 0; }
    memcpy(ImgLineProcInfo.pWriteBuff,ImgLineProcInfo.pLineData,
           ImgLineProcInfo.dwLineDataSize);
    *lines=1;
    return ImgLineProcInfo.dwLineDataSize;
}
typedef struct {
    struct {int wColorType;} devScanInfo;
    struct {struct {int lWidth;} ScanAreaByte;} scanInfo;
    struct {unsigned(*lpfnScanDecWrite)(void*,int*);} scanDec;
    struct {int bColorModel;} mfcModelInfo;
    struct {int bNoUseColorMatch;} modelConfig;
} Brother_Scanner;
static int GetStatusCode(char h) {return h;}
static void SetupImgLineProc(char h) {(void)h;}
static void ExecColorMatchingFunc(Brother_Scanner*s,LPBYTE p,int w,int n) {
    (void)s;(void)p;(void)w;(void)n;
}
'''
suffix = r'''
int main(void) {
    unsigned char whites[]={0,0,0};
    assert(StatusChk((char*)whites,sizeof(whites))==0);
    unsigned char status[]={0,0,0x81};
    assert(StatusChk((char*)status,sizeof(status))==1);
    unsigned char partial[]={1,4};
    assert(StatusChk((char*)partial,sizeof(partial))==0);
    unsigned char stream[]={0,1,4,0,11,22,33,44,0};
    unsigned char out[12]={0};
    Brother_Scanner scanner={0};
    scanner.devScanInfo.wColorType=COLOR_TG;
    scanner.scanInfo.ScanAreaByte.lWidth=4;
    scanner.scanDec.lpfnScanDecWrite=decode;
    lpRxBuff=stream;
    int written=0;
    WORD consumed=0;
    assert(ProcessMain(&scanner,sizeof(stream),3,(char*)out,&written,
                       &consumed)==SCAN_GOOD);
    assert(written==12);
    assert(consumed==sizeof(stream));
    assert(lRealY==3);
    assert(scan_packet_rows==3 && scan_white_rows==2);
    assert(scan_decoded_rows==1 && scan_decode_zero==0);
    unsigned char expected[]={255,255,255,255,11,22,33,44,255,255,255,255};
    assert(!memcmp(out,expected,sizeof(out)));
    unsigned char rejected[]={1,4,0,11,22,33,44,0x81};
    lpRxBuff=rejected; written=0; force_zero=1;
    assert(ProcessMain(&scanner,sizeof(rejected),4,(char*)out,&written,
                       &consumed)==(char)0x81);
    assert(scan_packet_rows==4 && scan_white_rows==2);
    assert(scan_decoded_rows==1 && scan_decode_zero==1);
    assert(scan_last_status==0x81 && consumed==sizeof(rejected));
    assert(written==0 && lRealY==3);
    puts("packet accounting and zero-output regression passed");
    return 0;
}
'''
with tempfile.TemporaryDirectory(prefix="brother-white-line-") as directory:
    test = Path(directory) / "test.c"
    binary = Path(directory) / "test"
    test.write_text(prefix + source[status_start:status_end] + source[start:end] + suffix)
    subprocess.run(["cc", "-g", "-fsanitize=address,undefined",
                    "-o", str(binary), str(test)], check=True)
    subprocess.run([str(binary)], check=True, env={**os.environ, "UBSAN_OPTIONS": "halt_on_error=1"})
