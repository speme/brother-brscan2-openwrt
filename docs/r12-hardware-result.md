# r12 MFC-7420 flatbed gray result

User's test7, 300 dpi, A4, NAPS2 over SANE:

```text
area: left=0 top=0 right=2480 bottom=3506 max_rows=4086
command: ESC X LF R=300,300 LF M=GRAY64 LF C=RLENGTH LF B=50 LF
         N=50 LF U=OFF LF P=OFF LF A=0,0,2480,3506 LF 0x80
output: rows=3506/3506 received_rows=3437
packets: raster_packets=3437 white_packets=0 decoded_rows=3437
         zero_output=0 last_status=0x80 pending_rx=0
```

For this stream every processed image packet produced one decoded row.
No white packets, decoder zero-output calls or pending receive bytes were
reported. Header `0x80` maps to SCAN_EOF in GetStatusCode. The 69 padding
rows are not explained by the raster clamp or decoder suppression in this
test. This does not independently verify every USB transfer byte; a wire
capture would be a stronger check of the packet parser.

r10's removal of P=OFF did not change the row count. r11's raster-limit
override never activated because the actual reported maximum was 4086.
The working hypothesis of a complete Windows edge scan remains untested
on hardware; Windows is not currently available to the user.

The next isolated experiment uses r12 unchanged and sets `[Driver]`
`compression=0` in `/usr/share/sane/brother/Brsane2.ini`. This is read by
GetCompressEnbale and changes the start command to C=NONE. It exercises a
different device output mode while retaining coordinates, resolution and
the existing packet counters. Back up the INI before the test, restart
sane-openwrt, and verify C=NONE in the logged command. Compression may
increase USB/network time; it is not a confirmed geometry fix.
