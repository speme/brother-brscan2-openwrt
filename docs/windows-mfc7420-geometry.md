# MFC-7420 Windows TWAIN geometry analysis

## Result

The supplied Windows TWAIN driver computes a 3437-row effective A4 scan at
300 dpi using its MFC-7420 model configuration. This is the same number as
`received_rows=3437` measured with the OpenWrt backend. The r9 output count
of 3506 rows includes padding; it is not evidence that 3506 rows of image
content came from the scanner.

This was verified by disassembly and by emulating the original Windows
machine code for two geometry routines. The device-property getter was
substituted with the model's INI values. Windows APIs, the WIA path, USB
transfers, and a complete Windows scanning session were not emulated.

## Inputs and provenance

Inputs are from the user's Windows driver directory. The INF explicitly
maps the MFC-7420 USB scanner to `VID_04F9&PID_0180&MI_01` and installs the
TWAIN model file `TWMF7420U.INI` together with `BrTwdScn.dll` and
`BrScnDev.dll`.

| Unpacked file | SHA-256 |
| --- | --- |
| `BrTwdScn.dll` | `c085f14823d3fd9026c396cfa346b53c34974f8fe32513f2e5f590a2315a8ccc` |
| `BrScnDev.dll` | `d30a41c1e890b37eb486ccc60aac98353c4ff61c0e8ee5cc1a586af5276a4252` |
| `TWMF7420U.INI` | `3815e0f7d96520dc3e74c0977d2df6f875decce1965d8ee34e5a41ae34f40315` |

The compressed inputs use SZDD variant A, not CAB. The repository provides
an unpacking script; no Windows binaries are redistributed here.

## Model parameters

The original INI contains these relevant values:

```ini
[Device]
Model=21
NoUseQcmd=1
MaxDocWidth=8500
MaxDocHeight=14000
ScanOriginX=77
ScanOriginY=118
MinScanWidth=16
MaxScanWidth=8347
MaxScanHeight=13780
LeftMargin=0
TopMargin=118
DocHandling=3
CornerMatchFB=1
ScanCmdAdjustWidth=2
```

Coordinates are thousandths of an inch. The conversion routine at VA
`0x1000a280` in `BrTwdScn.dll` evaluates, for the positive inputs tested:

```text
pixels = (dpi * milli_inches * 10 + 5000) / 10000
```

Division is integer division. Thus `ScanOriginY=118` is 2.9972 mm,
`TopMargin=118` is another 2.9972 mm, and `ScanOriginX=77` is 1.9558 mm.
These are driver calibration/cropping parameters, not independently
measured optical limits.

## Functions and recovered behavior

All addresses below refer to the preferred image base `0x10000000`.

| Module / VA | Function / observation |
| --- | --- |
| `BrScnDev.dll` / `0x10001da0` | `CDevProp::ReadDevScanAreaOrg` reads `ScanOriginX/Y` into area offsets `0x18/0x1c`. |
| `BrScnDev.dll` / `0x10001e70` | `CDevProp::ReadDevMarginSize` reads `LeftMargin/TopMargin` into offsets `0x24/0x28`. |
| `BrScnDev.dll` / `0x100015e0` | `GetDevScanAreaInfo` copies the 56-byte device-area structure. |
| `BrTwdScn.dll` / `0x1001c3f0` | `CScanParam::CalcScanAreaFromDocSize` subtracts Y origin and top margin from document height. |
| `BrTwdScn.dll` / `0x1001c290` | `CalcScanWidthFromDocSizeInch` handles horizontal extent and alignment. |
| `BrTwdScn.dll` / `0x1001c970` | `AdjustDeviceScanArea` clamps dimensions and applies the width adjustment rule. |
| `BrScnDev.dll` / `0x100016f0` | `GetDevMinScanWidth` returns the configured `MinScanWidth=16` step. |
| `BrScnDev.dll` / `0x10001740` | `GetScanWidthAdjustTypeInfo` returns `ScanCmdAdjustWidth=2`. |

`AdjustDeviceScanArea` uses the 16-unit step and rounds upward for adjustment
mode 2. When the X origin is zero it selects a dedicated right-edge cap;
otherwise it uses the regular scan-area cap. The Linux backend's zero-origin
16-pixel ceiling therefore matches the verified width-alignment rule. The
dedicated cap's exact source field is still under investigation.

The relevant height calculation in `CalcScanAreaFromDocSize` is equivalent
to the following for the supplied configuration:

```text
height = min(document_height - scan_origin_y - top_margin, max_scan_height)
top = 0
if top_margin > scan_origin_y:
    top = top_margin - scan_origin_y
    height -= top
bottom = top + height
```

The subtractions are visible at `0x1001c45d` and `0x1001c463`. With A4
approximated as `8268 x 11693` thousandths of an inch, the original binary
returns rectangle `(0, 0, 8191, 11457)`. Its original conversion routine
then returns **3437 rows** for 300 dpi. As a counterfactual check, setting
both Y parameters to zero gives **3508 rows** with the same machine code.
This counterfactual is an emulator check, not a tested device setting.

The SANE request previously used a bottom coordinate quantized to 0.1 mm,
giving a declared 3506 rows rather than the nominal A4 3508. That rounding
difference is separate from the effective Windows height of 3437 rows.

## What the hardware results do and do not prove

```text
r8: rows=3460/3506 bytes=8580800 row_bytes=2480
r9: rows=3506/3506 bytes=8694880 row_bytes=2480 received_rows=3437
```

The earlier end-of-page streaming bug is fixed in r9: it now delivers the
declared byte count. Its remaining rows are white padding. The count of 3437
received rows happens to equal the Windows emulator's computed A4 geometry,
but this match does not prove that Windows sent or received the same raster.
The geometry emulator supplies INI values to two Windows routines; it does
not run a Windows scan or inspect its USB stream.

The Windows INI sets `MaxDocHeight=14000`; after the Y-origin and top-margin
subtractions, a 14-inch rectangle becomes 13764 thousandths of an inch, or
about 4129 rows at 300 dpi. It sets `MaxDocWidth=8500`; the X-origin and
`MaxScanWidth=8347` leave 8347 thousandths of an inch, or about 2504 pixels
at 300 dpi before device adjustment. These Windows TWAIN model values are the
reference for the Linux port. They are geometry outputs, not a captured USB
transfer. The fixed upstream Linux constants (`MFCSCANFBHEIGHT=2910` and
3437 rows at 300 dpi) differ and should not override the Windows model without
evidence from the Windows DLL flow. See
[`mfc7420-windows-geometry-port.md`](mfc7420-windows-geometry-port.md) for
the port audit and known Linux deviations.

The hardware summaries distinguish the requested frame size from data that
arrived: `rows` is the SANE frame after padding, while `received_rows` and
`raster_packets` count decoded raster data. `row_bytes` is the output stride,
not proof of meaningful pixels over the full requested width.

For a scan-quality check, place a continuous frame several millimeters
inside the paper edges. A curve drawn on the paper edge cannot distinguish
driver cropping from the calibrated scan origin by itself.

## Reproduce

Use the original Windows files alongside this repository:

```sh
python3 tools/unpack_szdd.py ../brtwdscn.dl_ /tmp/brother-win/BrTwdScn.dll
python3 tools/unpack_szdd.py ../twmf7420u.in_ /tmp/brother-win/TWMF7420U.INI

python3 -m venv --system-site-packages /tmp/brother-reverse-env
/tmp/brother-reverse-env/bin/pip install lief==0.16.4 unicorn==2.1.4
/tmp/brother-reverse-env/bin/python tools/probe_windows_geometry.py \
  /tmp/brother-win/BrTwdScn.dll /tmp/brother-win/TWMF7420U.INI
```

The probe checks the DLL hash before using fixed function addresses. Its
only emulated external operation is the device-property getter, which
returns the supplied INI values. It asserts 3437 rows for the configured A4
rectangle, 4129 for Legal after the same offsets, and 3508 for an A4
zero-Y-offset counterfactual. It does not emulate the later device adjustment
or a complete Windows hardware scan.
