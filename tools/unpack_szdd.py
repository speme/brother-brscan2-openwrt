#!/usr/bin/env python3
"""Unpack a user-supplied SZDD 'A' file without executing its contents."""
from pathlib import Path
import argparse
import struct

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("source", type=Path)
parser.add_argument("output", type=Path)
args = parser.parse_args()
data = args.source.read_bytes()
if len(data) < 14 or data[:9] != b"SZDD\x88\xf0\x27\x33A":
    raise ValueError("Expected an SZDD variant A archive")
size = struct.unpack_from("<I", data, 10)[0]
window = bytearray(b" " * 4096)
position, offset = 4096 - 16, 14
result = bytearray()
while len(result) < size:
    if offset >= len(data):
        raise ValueError("Truncated SZDD flags")
    flags = data[offset]
    offset += 1
    for bit in range(8):
        if len(result) >= size:
            break
        if flags & (1 << bit):
            if offset >= len(data):
                raise ValueError("Truncated SZDD literal")
            value = data[offset]
            offset += 1
            result.append(value)
            window[position] = value
            position = (position + 1) & 4095
        else:
            if offset + 2 > len(data):
                raise ValueError("Truncated SZDD back-reference")
            low, high = data[offset:offset + 2]
            offset += 2
            start = low | ((high & 0xf0) << 4)
            for index in range((high & 15) + 3):
                value = window[(start + index) & 4095]
                result.append(value)
                window[position] = value
                position = (position + 1) & 4095
                if len(result) >= size:
                    break
args.output.parent.mkdir(parents=True, exist_ok=True)
args.output.write_bytes(result)
print(f"Unpacked {len(result)} bytes to {args.output}")
