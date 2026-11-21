# MFC-7420 scan geometry audit

## What the Windows files establish

`build_dir/windows/TWMF7420U.INI` is the TWAIN model configuration. Its
coordinates are thousandths of an inch:

```ini
MaxDocWidth=8500
MaxDocHeight=14000
ScanOriginX=77
ScanOriginY=118
MaxScanWidth=8347
MaxScanHeight=13780
LeftMargin=0
TopMargin=118
ScanCmdAdjustWidth=2
```

Disassembly of `BrTwdScn.dll` confirms that `CalcScanAreaFromDocSize`
subtracts the origin and margin from the requested document rectangle, then
limits it by the configured scan width and height. For an A4 request, the
vertical calculation is `11693 - 118 - 118 = 11457` thousandths of an inch;
at 300 dpi this is 3437 rows. This only explains the Windows **A4 geometry**.
The geometry emulator substitutes values from the INI and does not emulate
Windows USB transfers, the scan engine, or the final TWAIN image transfer.

The Windows TWAIN configuration explicitly permits a 14-inch document
rectangle (`MaxDocHeight=14000`). With the recorded origin and top margin,
Legal height becomes `14000 - 118 - 118 = 13764` thousandths of an inch.
`MaxScanHeight=13780` does not reduce that value. At 300 dpi the resulting
TWAIN height is about 4129 rows. Horizontally, `MaxDocWidth=8500`, minus the
77-thou X origin and limited by `MaxScanWidth=8347`, yields 8347 thou, or
about 2504 pixels at 300 dpi before the DLL's device-adjustment step.

These are the Windows model's calculated bounds. I extended
`tools/probe_windows_geometry.py` to execute the original DLL routines for
both A4 and Legal input. It returns Legal rectangle `(0, 0, 8347, 13764)` and
4129 rows at 300 dpi. The probe does not yet emulate the later
`AdjustDeviceScanArea` call or the USB transfer. The adjustment function calls
`CDevProp::GetDevMinScanWidth` (VA `0x100016f0`), which returns the INI value
`MinScanWidth=16`, and `GetScanWidthAdjustTypeInfo` (VA `0x10001740`), which
returns `ScanCmdAdjustWidth=2`. In `AdjustDeviceScanArea`, mode 2 rounds a
non-aligned extent up to that step. At X=0, it selects a dedicated right-edge
cap; otherwise it uses the regular scan-area cap. This confirms the Linux
16-pixel outward rounding for a zero-origin flatbed width. The exact value
feeding that final right-edge cap is still being traced.

## What the OpenWrt logs establish

The logs show two different quantities that were conflated in earlier notes:

* `scan area` and `start command A=...` are the **requested** raster bounds.
  Increasing `right` or `bottom` proves only that Linux sent a larger request.
* `raster_packets=3437` / `received_rows=3437` is the number of raster rows
  the backend decoded before the device's `0x80` end status. `rows=4200` is
  the SANE frame length, which the current EOF-padding code can fill with
  synthetic white rows. It does not mean the scanner returned 4200 image rows.
* `row_bytes` in the summary is the backend's output stride. It does not by
  itself prove that the scanner supplied meaningful pixels across that width.

The repeated 3437-row result after requests for 4086, 4200, and larger rows
therefore indicates that the device returned a shorter flatbed stream than
the requested SANE frame. The count is also exactly the Windows-calculated
A4 geometry above, but that numerical match does **not** establish that the
Windows driver requested or received the same stream. We have not captured a
Windows USB scan to compare.

The upstream backend source has fixed MFC flatbed constants
`MFCSCANFBHEIGHT=2910` (0.1 mm units) and `MFCSCAN600FBRASTER=6874` (600 dpi,
3437 rows at 300 dpi). These are software model limits, not an independent
measurement of this machine's glass. The live I-command values and observed
end-of-stream count disagree, so the I-command height should not be presented
as a verified physical limit without raw response/capture evidence.

## Confirmed implementation risks

1. The prior geometry patch hard-coded a 291 mm full-frame height and inferred
   Windows behavior from the A4 row-count coincidence. The current r28 source
   uses the Windows Legal effective height (`14000 - 118 - 118 = 13764` thou)
   and applies the document envelope only when the requested rectangle reaches
   the full scan range. Smaller top-left crops are not expanded.
2. The prior Linux patch also changed `dwMaxScanPixels` to permit overscan.
   That unrelated cap mutation has been removed. The 16-pixel outward width
   alignment follows Windows' `MinScanWidth=16` and adjustment mode 2. The
   final Windows right-edge cap value remains to be mapped exactly.
3. The source-specific SANE range update trusts the parsed I-command values.
   The reported flatbed 355.6 mm range differs from the Windows TWAIN
   calculated Legal height (349.6 mm after calibration offsets). An advertised
   option range is not proof of acquired image area; the Windows values should
   take precedence for this port, and the discrepancy should be resolved by
   following the Windows DLL path.
4. `InitOptions` used a function-local `static` default rectangle and then
   reduced its bottom-right values to each device's reported range. That
   mutation persisted across later opens, so a smaller-range device could
   permanently narrow subsequent defaults. r28 makes the rectangle local to
   each call and restores the model defaults on every open.
5. Padding early EOF to the requested frame makes files rectangular but
   hides the device's shorter data stream by adding white rows. It should be
   kept distinct from image data and must not be used to claim full-area
   scanning.

## Conclusion and next evidence needed

There were definite errors in the previous interpretation and experimental
Linux geometry changes. The current patch ports the verified Legal height and
16-pixel zero-origin width alignment, and preserves smaller crops. The exact
final right-edge cap and transfer behavior remain to be mapped. Enlarging
`A=` alone cannot prove that the device returned all data.
