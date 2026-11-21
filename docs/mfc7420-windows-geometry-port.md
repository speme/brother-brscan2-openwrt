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

The Linux backend applies the same values to the MFC-7420 flatbed's full-frame SANE rectangle before converting 0.1 mm coordinates to dots. It retains sub-0.1 mm
precision through the correction and rounds the resulting far edges outward,
so 16-dot horizontal alignment does not unexpectedly drop a full 16-dot
step. The values live in `/etc/sane.d/brother2-geometry.conf`; missing entries fall back to the Windows values. Set the two origins and two margins to zero to disable the geometry correction; maximum-dimension caps remain active. The rule is gated to USB product `04f9:0180`, flatbed source, and a zero left/top request; other models, ADF scans and cropped regions are left untouched.

For an A4 request at 300 dpi, the expected calibrated millimeter bounds are about 208.0 x 291.0 mm. A larger request is capped at the Windows model maximum of about 212.0 x 350.0 mm before correction, then at the scanner-reported limits. After the backend's 16-dot horizontal alignment, the A4 frame should be approximately 2464 x 3437 pixels. This agrees with the measured 3437 raster rows and the original TWAIN emulator's 3437-row A4 geometry. It removes the synthetic white right/bottom extent from the SANE frame; it cannot recreate pixels the device did not transmit.

## Why this changes the scan origin handling

The USB `A=left,top,right,bottom` field describes the device scan rectangle. `A=0,0,...` is already the earliest left/top coordinate used by this backend. The Windows `ESC S ... FB` command selects the flatbed source; it does not set a spatial origin. The Windows model values are calibration geometry, so the Linux port changes the frame's calibrated bounds rather than shifting returned pixel rows after the scan.

The former r13 experiment shifted decoded pixels right and down. It did not change the USB scan command and was based on synthetic WIA model dimensions. That post-read shift has been removed.

## Maximum document size versus active scan geometry

Brother's MFC-7420 user guide lists the flatbed glass size as 215.9 x 297 mm. That is the physical document limit. The INI's `MaxScanWidth=8347` means about 212.0 mm. `MaxScanHeight=13780` means about 350.0 mm and is not the flatbed glass length; the Windows configuration also covers the ADF path. The Linux backend applies these Windows model caps and continues to use the scanner's queried pixel/raster limits for device clamping. The live flatbed raster limit is lower than the Windows maximum height. The runtime logs currently show a reported `max_rows=4086`, which is a device clamp value, not the number of rows returned in the A4 scan (3437).

Sources: `build_dir/windows/TWMF7420U.INI`, disassembly of `BrTwdScn.dll` routines `0x1001c290` and `0x1001c3f0`, `docs/windows-mfc7420-geometry.md`, and Brother's [MFC-7420 User's Guide](https://www.brother-usa.com/-/media/brother/product-catalog-media/documents/2020/08/17/13/31/um_mfc7420_fr.pdf).
