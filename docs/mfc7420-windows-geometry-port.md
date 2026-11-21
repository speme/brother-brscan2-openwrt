# Porting the MFC-7420 Windows geometry to SANE

## Windows model parameters

The supplied `TWMF7420U.INI` has these `[Device]` values. Its coordinate unit is one thousandth of an inch:

```ini
ScanOriginX=77
ScanOriginY=118
LeftMargin=0
TopMargin=118
MaxScanWidth=8347
MaxScanHeight=13780
```

The TWAIN DLL's geometry routines subtract `ScanOriginX + LeftMargin` from the document's right edge and `ScanOriginY + TopMargin` from its bottom edge. If a margin exceeds the corresponding origin, the near edge begins at `Margin - Origin`. For the MFC-7420 defaults the near edge stays at `(0,0)` and the far edge is reduced by 77 and 236 thousandths of an inch. At 300 dpi that is about 23 horizontal dots and 71 vertical dots.

The Linux backend retains the Windows crop values, but full-frame requests
whose top-left is `(0,0)` default to the calibrated usable area. Earlier r21-r24
builds probed beyond the nominal width to investigate the origin offset. That
made a 217.9 mm / 2576-pixel frame, wider than the 215.9 mm (8.5 in) Legal and
Letter page width. r25 sets the geometric request to 8500 thousandths of an
inch (215.9 mm) and rounds the right edge outward to the scanner's 16-pixel
boundary. At 300 dpi, the 2550-pixel physical width therefore becomes 2560
columns, about 0.85 mm of alignment margin. The backend raises the queried
horizontal pixel cap to match, implementing the effect of Windows
`ScanCmdAdjustWidth=2` for a zero left edge. Set
`ExpandFullFrame=0` in
`/etc/sane.d/brother2-geometry.conf` to apply the Windows origin/margin crop
and retain the queried width cap. This applies only to USB product
`04f9:0180`, flatbed source, and a zero left/top request; other models and ADF
scans are untouched.

With r21 full-range mode enabled, the nominal request was about 217.9 x 350.0 mm.
`MaxScanHeight=13780` is the 350 mm model/ADF limit. r23 requested Legal
length (355.6 mm) and raised `dwMaxScanRaster` to 4200 rows at 300 dpi. The
device still ended normally after exactly 3437 raster packets. This matches
the backend's original `MFCSCAN600FBRASTER=6874` limit divided by two at 300 dpi
and the calibrated flatbed length `MFCSCANFBHEIGHT=2910` (291 mm). The Windows
`ScanOriginY + TopMargin=236` thou subtracts about 6 mm from the 297 mm glass.
r24 therefore uses 11457 thou (291 mm) as the flatbed output height and leaves
the raster cap intact, avoiding synthetic white rows beyond the received scan.
The r25 frame width is 2560 columns at 300 dpi, aligned outward from the nominal
2550-pixel Legal/Letter width.
The r20 hardware scan accepted
`A=0,0,2544,4086`, reported `row_bytes=2544`, `max_pixels=2550`, and returned
3437 raster rows. With the old 4086-row request, 649 rows were synthesized as
white at EOF; the r23 4200-row request produced 763 white rows. r24's 291 mm
frame is 3437 rows at 300 dpi, aligning the SANE frame with the received
flatbed raster. r21 tests the next
horizontal range beyond the glass; its aligned width was 2576 dots. That sample
only showed the edge marks within the oversized frame; it did not establish
that 2576 dots was the correct Legal/Letter width.
The new `brother2 decoder summary` log reports decoded row lengths and the
rightmost nonwhite pixel for a hardware-side comparison.

## Why this changes the scan origin handling

The USB `A=left,top,right,bottom` field describes the device scan rectangle. `A=0,0,...` is already the earliest left/top coordinate used by this backend. The Windows `ESC S ... FB` command selects the flatbed source; it does not set a spatial origin. The Windows model values are calibration geometry, so the Linux port changes the frame's calibrated bounds rather than shifting returned pixel rows after the scan.

The former r13 experiment shifted decoded pixels right and down. It did not change the USB scan command and was based on synthetic WIA model dimensions. That post-read shift has been removed.

## Maximum document size versus active scan geometry

Brother's MFC-7420 user guide lists the flatbed glass size as 215.9 x 297 mm. That is the physical document limit. The INI's `MaxScanWidth=8347` means about 212.0 mm. `MaxScanHeight=13780` means about 350.0 mm and is not the flatbed glass length; the Windows configuration also covers the ADF path. The Linux backend applies these Windows model caps and continues to use the scanner's queried pixel/raster limits for device clamping. The live flatbed raster limit is lower than the Windows maximum height. The runtime logs currently show a reported `max_rows=4086`, which is a device clamp value, not the number of rows returned in the A4 scan (3437).

Sources: `build_dir/windows/TWMF7420U.INI`, disassembly of `BrTwdScn.dll` routines `0x1001c290` and `0x1001c3f0`, `docs/windows-mfc7420-geometry.md`, and Brother's [MFC-7420 User's Guide](https://www.brother-usa.com/-/media/brother/product-catalog-media/documents/2020/08/17/13/31/um_mfc7420_fr.pdf).
