#!/usr/bin/env python3
"""Exercise the actual PageScan tail with sub-raster SANE read buffers.

Usage: python3 tests/eof-padding.py path/to/brother_scanner.c
"""
from pathlib import Path
import subprocess
import sys
import tempfile

s = Path(sys.argv[1]).read_text(errors="replace")
start = s.index("\tif ( nAnswer == SCAN_EOF || nAnswer == SCAN_MPS )",
                s.index("memmove( lpFwBuf, lpFwTempBuff, *lpFwLen)"))
end = s.index("\treturn rc;\n}", start) + len("\treturn rc;\n}")
prefix = r'''
#include <assert.h>
#include <stdint.h>
#include <string.h>
#include <stdio.h>
typedef int32_t LONG;
enum {SCAN_EOF=1, SCAN_MPS, SCAN_CANCEL, SCAN_NODOC, SCAN_DOCJAM,
      SCAN_COVER_OPEN, SCAN_SERVICE_ERR, SCAN_DUPLEX_NORMAL};
enum {SANE_STATUS_GOOD=0, SANE_STATUS_EOF=5, SANE_STATUS_CANCELLED,
      SANE_STATUS_IO_ERROR, SANE_STATUS_NO_DOCS, SANE_STATUS_JAMMED,
      SANE_STATUS_COVER_OPEN, SANE_STATUS_DUPLEX_ADVERSE};
#define FALSE 0
#define TRUE 1
#define COLOR_TG 4
#define WriteLog(...) ((void)0)
static LONG lRealY, scan_received_rows;
static unsigned long scan_packet_rows, scan_white_rows, scan_decode_zero, scan_decoded_rows;
static unsigned scan_last_status;
static unsigned long dwRxTempBuffLength;
static size_t scan_padding_remaining;
static int scan_padding_active, nFwLenTotal, FwTempBuffLength;
typedef struct {
    struct {int wColorType;} devScanInfo;
    struct {struct {int lWidth;} ScanAreaByte;
            struct {int lHeight;} ScanAreaSize;} scanInfo;
    struct {int nPageCnt,bScanning,bCanceled,bEOF;} scanState;
} Brother_Scanner;
static int finish(Brother_Scanner *this,char *lpFwBuf,int nMaxLen,int *lpFwLen) {
    int rc=SANE_STATUS_GOOD,nAnswer=SCAN_EOF;
    *lpFwLen=0;
'''
suffix = r'''
int main(void) {
    const int capacities[]={1,1024,2480,65536};
    for (unsigned k=0;k<sizeof(capacities)/sizeof(capacities[0]);k++) {
        Brother_Scanner scanner={0};
        scanner.devScanInfo.wColorType=COLOR_TG;
        scanner.scanInfo.ScanAreaByte.lWidth=2480;
        scanner.scanInfo.ScanAreaSize.lHeight=3506;
        scanner.scanState.bScanning=TRUE;
        lRealY=3437;
        nFwLenTotal=3437*2480;
        scan_padding_active=0;
        scan_padding_remaining=0;
        FwTempBuffLength=0;
        unsigned char out[65536];
        while (nFwLenTotal<3506*2480) {
            int length=-1;
            memset(out,0,sizeof(out));
            assert(finish(&scanner,(char*)out,capacities[k],&length)==SANE_STATUS_GOOD);
            assert(length>0 && length<=capacities[k]);
            assert(!scanner.scanState.bEOF);
            for (int i=0;i<length;i++) assert(out[i]==255);
        }
        assert(nFwLenTotal==3506*2480);
        assert(lRealY==3506);
        int length=-1;
        assert(finish(&scanner,(char*)out,capacities[k],&length)==SANE_STATUS_EOF);
        assert(length==0 && scanner.scanState.bEOF);
    }
    puts("EOF padding regression passed for 1/1024/2480/65536-byte reads");
    return 0;
}
'''
with tempfile.TemporaryDirectory(prefix="brother-eof-") as directory:
    test = Path(directory) / "test.c"
    binary = Path(directory) / "test"
    test.write_text(prefix + s[start:end] + suffix)
    subprocess.run(["cc", "-g", "-fsanitize=address,undefined",
                    "-o", str(binary), str(test)], check=True)
    subprocess.run([str(binary)], check=True)
