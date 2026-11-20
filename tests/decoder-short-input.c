#include <assert.h>
#include <stdint.h>
#include <string.h>
#include "brother_scandec.h"
#include "brother_deccom.h"

int main(void) {
  SCANDEC_OPEN o = {0};
  o.nColorType = SCCLR_TYPE_TG; o.dwInLinePixCnt = 4;
  assert(ScanDecOpen(&o));
  assert(ScanDecPageStart());
  unsigned char in[] = {3, 11, 22, 33, 44};
  unsigned char out[4] = {0}; int lines = -1;
  SCANDEC_WRITE w = {0}; w.nInDataComp=SCIDC_PACK; w.nInDataKind=SCIDK_MONO;
  w.pLineData=(CHAR*)in; w.pWriteBuff=(CHAR*)out; w.dwWriteBuffSize=sizeof(out);
  for (unsigned i=0; i<2; i++) {
    w.dwLineDataSize=i;
    assert(ScanDecWrite(&w, &lines)==4);
    assert(lines==1);
    for (unsigned j=0; j<sizeof(out); j++) assert(out[j]==255);
  }
  w.dwLineDataSize=3;
  assert(ScanDecWrite(&w,&lines)==4);
  assert(lines==1);
  assert(out[0]==11 && out[1]==22 && out[2]==255 && out[3]==255);
  w.dwLineDataSize=sizeof(in); assert(ScanDecWrite(&w,&lines)==4); assert(lines==1); assert(!memcmp(out,in+1,4));
  assert(ScanDecClose());
  assert(ScanDecOpen(&o)); unsigned char table[16] = {0}; ScanDecSetTblHandle(0,table); assert(ScanDecPageStart());
  w.dwLineDataSize=0; assert(ScanDecWrite(&w,&lines)==4); w.dwLineDataSize=1; assert(ScanDecWrite(&w,&lines)==4);
  assert(ScanDecClose());
  assert(!ScanDecOpen(0)); o.dwInLinePixCnt=0; assert(!ScanDecOpen(&o));
  return 0;
}
