# Windows WIA command builder

The working hypothesis is that the complete Windows driver can preserve
the paper-edge markings. This is a hypothesis for investigation, not a
physical Windows scan result. The isolated TWAIN calculation documented
in `windows-mfc7420-geometry.md` cannot settle that question.

## Reproducible command extraction

`tools/probe_windows_wia_command.py` executes the original x86
`BrWia09a.dll` command builder at VA `0x1c3168de` in Unicorn. The analyzed
DLL SHA-256 is
`43a4bd4bf186a77f6a2328589085e0ef1c17870e3e0d691f1b1729a3f08231ff`.
The probe rejects other builds. It replaces logging, registry lookup
(duplex unavailable), stack-cookie checking, and `lstrlenA`; the original
command-building, string-copying and numeric-formatting code executes.
It performs no USB access.

With synthetic 300 dpi gray, uncompressed, neutral brightness/contrast,
and rectangle `(0, 0, 2480, 3506)` parameters, it generates:

```text
ESC X LF
R=300,300
M=GRAY64
C=NONE
B=50
N=50
U=OFF
A=0,2480,0,3506

0x80
```

The builder emits no `P=OFF` field, whereas the Linux backend includes
that field. This is a confirmed command difference for the tested branch,
but it does not establish that photo mode causes the missing rows.
The rectangle is supplied directly to the builder; it is not a recovered
Windows application's final rectangle.

Run with the original unpacked Windows DLL:

```sh
/tmp/brother-reverse-venv/bin/python tools/probe_windows_wia_command.py \
  /tmp/brother-win-reverse/x86/brwia09a.dll
```

## Independent WIA geometry path

Disassembly of `0x1c313cdd` shows four separate offsets at object fields
`0x106c`, `0x1070`, `0x1074`, `0x1078` (left, right, top, bottom).
The function converts a hard-coded vertical origin of 118 thousandths of
an inch into a top offset when the requested top is zero. It subtracts
the four offsets from the requested device width and height. Its maximum
document and scan sizes come from object fields `0x10cc..0x10e8`, selected
by source and capability flags. Their actual MFC-7420 initialization must
be traced before treating a synthetic geometry calculation as model data.

`BrScnDevicePageStart` checks the empty-region flag at `0x1094` and the top
offset separately. This confirms a canvas-placement path that needs to be
compared with the portable backend; padding or positioning alone does not
recover image data that the device never returned.

The next decisive comparison is the final rectangle and complete start
command after model initialization, followed by a controlled device scan.
No default geometry or released APK has been changed based only on this
command-builder probe.
