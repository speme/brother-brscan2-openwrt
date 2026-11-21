# Brother brscan2 for OpenWrt

This package targets OpenWrt 25.12.6 on Lenovo Newifi Y1 (`ramips/mt7620`,
`mipsel_24kc`) and adds Brother's SANE `brscan2` backend for MFC-7420 USB
scanners (`04f9:0180`). The prebuilt OpenWrt APK and Ubuntu test DEB are
attached to the GitHub release; build them from source with the instructions
below for other matching environments.

The original Brother archive includes proprietary prebuilt decoder libraries.
This package replaces them with portable C code from the GPL-2.0
`dmikushin/brscan` project, and uses Brother's backend source and model data.
The resolution conversion replacement is currently a passthrough and has not
been validated against the physical scanner. Treat the package as experimental.

A separate native Ubuntu 26.04 x86_64 test DEB is attached to the GitHub
release. The locally compiled backend was loaded from a temporary SANE
directory and completed a 100 dpi, 30 mm square grayscale scan on an attached
MFC-7420. The resulting PNM file was 1.7 KB. The OpenWrt package has been
exercised on a Lenovo Newifi Y1 with OpenWrt
25.12.6 and a Brother MFC-7420 (`04f9:0180`). A gray scan through the network
SANE service succeeded after granting the `scanner` group USB-node access.
Release `r2` installs the USB ID marker so the OpenWrt SANE hotplug handler
grants that access automatically on future USB attach events. Release `r3`
assembles separate R, G, and B scan lines into interleaved RGB rows and swaps
BGR input when needed. A full-page MFC-7420 color scan confirmed that the
three-band output is fixed. Release `r4` adds Brother's MFC-7420 color LUT at
`GrayCmData/ALL/brmsl08f.cm`; the `.cm` file retains Brother's license.
Release `r5` guards short compressed lines and allocation failures. It has
been checked with synthetic decoder inputs; hardware testing is still needed.
It also corrects the timestamp argument type and bounds formatted diagnostic
messages in the Brother backend on 32-bit OpenWrt.
Release `r6` also bounds scan-command logging and fixes its handling of
nonprintable bytes.
Release `r7` fixes output accounting for complete white rows returned by the
scanner. The old packet handler advanced the destination pointer without
adding the row to the output byte count, which could drop rows and truncate
page content. A synthetic packet regression fails on the upstream handler
and passes on the patched handler with sanitizers. Hardware confirmation is
still required after installing this release.
The reported 300 dpi edge problem persisted with `r7`: the backend still
advertised 3506 rows but delivered 3460 rows. `r8` is a test build that pads
short grayscale rasters to the configured row width and reports row/byte
counts at the end of a scan. Empty and truncated input regression cases
pass with sanitizers; a new hardware scan is required to confirm the result.
`r8` also returned 3460/3506 rows on the scanner. `r9` fixes a separate
premature EOF in end-of-page padding: read buffers smaller than a raster
were rounded down to zero rows and interpreted as EOF. Padding now streams
across arbitrary positive read sizes. The summary includes `received_rows`
before padding, so a correctly sized output is distinguishable from missing
image content. This fix does not recover content the device did not send.

`r10` is an experimental comparison build: it omits the `P=OFF` scan-command
field, matching the analyzed Windows WIA command-builder branch. Geometry,
decoding, and EOF padding remain as in r9. Whether this changes the missing
edge content requires a hardware scan; it is not a confirmed fix.

To install the native test build on this Ubuntu x86_64 system:

```sh
sudo dpkg -i output/brother-brscan2-local_0.2.5-1_amd64.deb
scanimage -L
scanimage --format=pnm --mode Gray --resolution 100 -x 30 -y 30 > /tmp/mfc7420-test.pnm
```

Remove it with `sudo dpkg --purge brother-brscan2-local`.

## Install on the router

Copy the APK to the router (for example with `scp`), then run as root:

```sh
apk update
apk add libsane sane-frontends libusb-compat4 usbutils
apk add --allow-untrusted /tmp/brother-brscan2-0.2.5-r19.apk
```

The router must have access to its configured OpenWrt package repositories to
install the dependencies. `--allow-untrusted` is needed because this locally
built APK is not signed by an OpenWrt repository key.

Connect the MFC-7420 directly to the router's USB port, then check:

```sh
lsusb
scanimage -L
```

The package registers USB ID `04f9:0180` with OpenWrt's SANE hotplug handler,
which grants the `scanner` group access to the device node. This is required
because `saned` runs as `saned:scanner`. It applies when the scanner is first
attached after installation; if it is already attached, unplug and reconnect
it or grant its current USB node to group `scanner` manually.

The USB listing should contain `04f9:0180`, and `scanimage -L` should list a
Brother scanner. To perform a quick test scan:

```sh
scanimage --format=pnm > /tmp/mfc7420-test.pnm
ls -lh /tmp/mfc7420-test.pnm
```

If detection fails, collect `lsusb` and `scanimage -L` output. Debug logging
has caused `scanimage` to segfault on the tested OpenWrt router and its cause
has not yet been established. Scaling is not implemented by this decoder;
scan resolutions other than those tested may produce incorrect results.

For the 300 dpi flatbed edge issue, see
[Windows MFC-7420 geometry analysis](docs/windows-mfc7420-geometry.md).
The supplied Windows TWAIN DLL computes the same 3437-row effective A4
height observed from the device; r9 pads that input to the SANE frame size.
The analysis includes the model parameters and a machine-code emulator
probe, and distinguishes the range calculation from the unverified final
Windows output layout.

## Build

Build with the matching OpenWrt 25.12 SDK and `packages` feed enabled:

```sh
make package/libs/libusb-compat/compile V=s
make package/utils/sane-backends/compile V=s
make package/feeds/custom/brother-brscan2/compile V=s
```

`tests/decoder-short-input.c` exercises short PackBits input and a normal
decoded line. Compile it with the decoder sources and Brother's
`backend_src/brother_dtype.h` from the source archive, keeping the expected
`libbrscandec2` and `libsane-brother` directory layout. Running with AddressSanitizer
and UndefinedBehaviorSanitizer is recommended on a development machine.

To test the white-row fix against the prepared upstream source:

```sh
python3 tests/white-line-accounting.py path/to/brscan/backend_src/brother_scanner.c
python3 tests/eof-padding.py path/to/brscan/backend_src/brother_scanner.c
```

## Licensing

Repository-maintained packaging, integration, and documentation contributions
are licensed under LGPL-2.1-or-later; see [`LICENSE`](LICENSE). Third-party
components keep their original terms: the replacement libraries are GPL-2.0
(see `files/COPYING` and `files/COPYING.brscan`), and Brother source and data
retain Brother's open license and notices (see `files/COPYING.brother` and the
upstream source headers). The repository LGPL notice does not replace those
component-specific licenses.

`r10` hardware feedback: received_rows remains 3437, so omitting P=OFF did
not improve the tested page. `r11` restores that field and tests full A4
height (up to 297 mm) only for MFC-7420 flatbed regions otherwise clamped
by the reported raster limit. It logs reported and requested limits. This
is experimental; the device may still terminate before the requested end.

`r11` hardware feedback showed `max_rows=4086` and `bottom=3506`,
with 3437 decoded rows again. The 3437 default-limit hypothesis was not
confirmed: the override never triggered. `r12` removes that override and
adds actual start-command logging plus counts of raster packets, white
packets, decoded rows, zero-output decoder calls, final status header and
pending receive bytes. `received_rows` is decoded output before padding,
not an independent USB raster count. These diagnostics distinguish a short
input stream from decoder row loss; r12 is not an edge-content fix.

During r12 regression testing, UBSan exposed unaligned 16-bit packet-length
loads. These are now assembled from bytes, including receive-buffer status
checks and raster processing. The all-white-buffer regression also exposed
that `StatusChk` advanced its pointer without decrementing its remaining
byte count; it now consumes one byte per white packet. ASan/UBSan tests cover
all-white buffers, partial headers, mixed image/white packets, zero-output
decode calls and status tracking. Neither bug is yet established as the
cause of the measured 69-row deficit.

`r19` expands MFC-7420 flatbed requests whose top-left is `(0,0)` to the
Windows model maximum, 212.0 x 350.0 mm. In this exploratory mode it also
raises the backend's queried horizontal pixel cap to the corresponding model
limit, implementing the effect of Windows `ScanCmdAdjustWidth=2` for a zero
left edge. It rounds the 212.0138 mm Windows width outward to 212.1 mm so
0.1 mm quantization does not round below that limit. The scanner may still
clamp the request; the logs now include
`max_pixels` to show the cap passed to the device-area calculation. Set
`ExpandFullFrame=0` in `/etc/sane.d/brother2-geometry.conf` to restore the
Windows origin/margin crop and queried device cap. Other scanners and requests
with a nonzero top-left are unchanged.

The settings are in `/etc/sane.d/brother2-geometry.conf`, registered as a
package conffile. Set `ExpandFullFrame=0` to apply the Windows origin/margin
crop. The settings apply only to MFC-7420 flatbed scans whose requested
top-left is `(0,0)`. The log reports `brother2 MFC-7420 TWAIN geometry`. See
[`docs/mfc7420-windows-geometry-port.md`](docs/mfc7420-windows-geometry-port.md)
for the reverse-engineering evidence and remaining hardware limits.
