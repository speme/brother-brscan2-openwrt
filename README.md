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
grants that access automatically on future USB attach events.

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
apk add --allow-untrusted /tmp/brother-brscan2-0.2.5-r2.apk
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

If detection fails, collect `lsusb`, `scanimage -L`, and
`SANE_DEBUG_BROTHER2=128 scanimage -L` output. Do not expect color or scaled
resolution modes to work correctly until tested on the device.

## Build

Build with the matching OpenWrt 25.12 SDK and `packages` feed enabled:

```sh
make package/libs/libusb-compat/compile V=s
make package/utils/sane-backends/compile V=s
make package/feeds/custom/brother-brscan2/compile V=s
```

## Licensing

Repository-maintained packaging, integration, and documentation contributions
are licensed under LGPL-2.1-or-later; see [`LICENSE`](LICENSE). Third-party
components keep their original terms: the replacement libraries are GPL-2.0
(see `files/COPYING` and `files/COPYING.brscan`), and Brother source and data
retain Brother's open license and notices (see `files/COPYING.brother` and the
upstream source headers). The repository LGPL notice does not replace those
component-specific licenses.
