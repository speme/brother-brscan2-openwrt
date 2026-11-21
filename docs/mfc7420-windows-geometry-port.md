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
whose top-left is `(0,0)` default to an expanded exploratory range. r20
requested the 215.9 mm flatbed glass width and the 350.0 mm model height.
r21 extends the horizontal request by Windows `ScanOriginX=77` (1.9558 mm),
to 8577 thousandths of an inch, about 217.9 mm. This probes whether that
origin offset corresponds to usable area outside the nominal glass width.
The backend raises the queried horizontal pixel cap and rounds width outward
through SANE's 0.1 mm units, testing `ScanCmdAdjustWidth=2` for a zero left
edge. The scanner may return blank overscan or clamp the request. Set
`ExpandFullFrame=0` in
`/etc/sane.d/brother2-geometry.conf` to apply the Windows origin/margin crop
and retain the queried width cap. This applies only to USB product
`04f9:0180`, flatbed source, and a zero left/top request; other models and ADF
scans are untouched.

With r21 full-range mode enabled, the nominal request was about 217.9 x 350.0 mm.
`MaxScanHeight=13780` is the 350 mm model/ADF limit. r22 temporarily limited
the flatbed request to the 297 mm glass length. r23 probes US Legal at 14000
thousandths of an inch (355.6 mm), raising `dwMaxScanRaster` to match the
requested 4200 rows at 300 dpi. Brother documents the glass as 297 mm, so the
extra request tests carriage travel beyond the glass; it does not imply the
area beyond the glass can image a page. The r20 hardware scan accepted
`A=0,0,2544,4086`, reported `row_bytes=2544`, `max_pixels=2550`, and returned
3437 raster rows. With the old 4086-row request, 649 rows were synthesized as
white at EOF. r22 reduced that padding; the r23 Legal probe will report actual
received rows separately from any EOF padding, showing whether raising the
device clamp changes carriage output. r21 tests the next
horizontal range beyond the glass; its aligned width is 2576 dots. Its test
image is 2576 pixels wide and contains edge marks through x=2572, so the
current sample does not show horizontal clipping in the emitted SANE frame.
The new `brother2 decoder summary` log reports decoded row lengths and the
rightmost nonwhite pixel for a hardware-side comparison.

## Why this changes the scan origin handling

The USB `A=left,top,right,bottom` field describes the device scan rectangle. `A=0,0,...` is already the earliest left/top coordinate used by this backend. The Windows `ESC S ... FB` command selects the flatbed source; it does not set a spatial origin. The Windows model values are calibration geometry, so the Linux port changes the frame's calibrated bounds rather than shifting returned pixel rows after the scan.

The former r13 experiment shifted decoded pixels right and down. It did not change the USB scan command and was based on synthetic WIA model dimensions. That post-read shift has been removed.

## Maximum document size versus active scan geometry

Brother's MFC-7420 user guide lists the flatbed glass size as 215.9 x 297 mm. That is the physical document limit. The INI's `MaxScanWidth=8347` means about 212.0 mm. `MaxScanHeight=13780` means about 350.0 mm and is not the flatbed glass length; the Windows configuration also covers the ADF path. The Linux backend applies these Windows model caps and continues to use the scanner's queried pixel/raster limits for device clamping. The live flatbed raster limit is lower than the Windows maximum height. The runtime logs currently show a reported `max_rows=4086`, which is a device clamp value, not the number of rows returned in the A4 scan (3437).

Sources: `build_dir/windows/TWMF7420U.INI`, disassembly of `BrTwdScn.dll` routines `0x1001c290` and `0x1001c3f0`, `docs/windows-mfc7420-geometry.md`, and Brother's [MFC-7420 User's Guide](https://www.brother-usa.com/-/media/brother/product-catalog-media/documents/2020/08/17/13/31/um_mfc7420_fr.pdf).
