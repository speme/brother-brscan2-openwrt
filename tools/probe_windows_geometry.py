#!/usr/bin/env python3
"""Emulate two geometry routines from the supplied 2009 TWAIN DLL.

Requires lief and unicorn. This substitutes the device-property getter with
values read from TWMF7420U.INI; it does not emulate Windows or USB transfers.
"""
from pathlib import Path
import argparse
import configparser
import hashlib
import json
import struct

import lief
from unicorn import Uc, UC_ARCH_X86, UC_MODE_32, UC_HOOK_CODE
from unicorn.x86_const import UC_X86_REG_ECX, UC_X86_REG_ESP

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("dll", type=Path)
parser.add_argument("ini", type=Path)
args = parser.parse_args()
expected = "c085f14823d3fd9026c396cfa346b53c34974f8fe32513f2e5f590a2315a8ccc"
if hashlib.sha256(args.dll.read_bytes()).hexdigest() != expected:
    raise ValueError("DLL differs from the analyzed build; routine addresses may differ")
cfg = configparser.ConfigParser()
cfg.read(args.ini)
device = cfg["Device"]
area = [device.getint("MaxDocWidth"), device.getint("MaxDocHeight"), 1,
        device.getint("MaxScanWidth"), device.getint("MaxScanHeight"), 1,
        device.getint("ScanOriginX"), device.getint("ScanOriginY"), 1,
        device.getint("LeftMargin"), device.getint("TopMargin"), 1,
        device.getint("MinScanWidth"), 0]

pe = lief.PE.parse(str(args.dll))
base = pe.optional_header.imagebase
cpu = Uc(UC_ARCH_X86, UC_MODE_32)
cpu.mem_map(base, (pe.optional_header.sizeof_image + 4095) & ~4095)
for section in pe.sections:
    cpu.mem_write(base + section.virtual_address, bytes(section.content))
cpu.mem_map(0x20000000, 0x10000)  # Mock objects and outputs
cpu.mem_map(0x30000000, 0x1000)  # Device-property hook and return sentinel
cpu.mem_map(0x40000000, 0x10000)  # Stack

def pack(*values):
    return struct.pack("<" + "I" * len(values), *values)

cpu.mem_write(0x20000008, pack(0x20001000))
cpu.mem_write(0x20001000, pack(0x20002000))
cpu.mem_write(0x20002044, pack(0x30000000))
cpu.mem_write(0x30000000, b"\xc2\x04\x00")  # thiscall ret 4
cpu.mem_write(0x30000010, b"\x90")

def hook(uc, address, size, user_data):
    if address == 0x30000000:
        sp = uc.reg_read(UC_X86_REG_ESP)
        target = struct.unpack("<I", uc.mem_read(sp + 4, 4))[0]
        uc.mem_write(target, pack(*area))
    if address == 0x30000010:
        uc.emu_stop()

cpu.hook_add(UC_HOOK_CODE, hook)

def call(rva, parameters):
    stack = 0x40008000
    cpu.mem_write(stack, pack(0x30000010, *parameters))
    cpu.reg_write(UC_X86_REG_ESP, stack)
    cpu.reg_write(UC_X86_REG_ECX, 0x20000000)
    cpu.emu_start(base + rva, 0, count=100000)

def probe():
    # 8268 x 11693 in 0.001 inch units approximates 210 x 297 mm.
    call(0x1c3f0, [8268, 11693, 1, 0x20003000])
    rect = struct.unpack("<4I", cpu.mem_read(0x20003000, 16))
    call(0xa280, [300, rect[3] - rect[1], 0x20004000])
    rows = struct.unpack("<I", cpu.mem_read(0x20004000, 4))[0]
    return {"rectangle_milli_inch": rect, "rows_300dpi": rows}

result = {"dll_sha256": expected, "model_configuration": probe()}
area[7] = area[10] = 0
result["counterfactual_zero_y_origin_and_margin"] = probe()
assert result["model_configuration"]["rows_300dpi"] == 3437
assert result["counterfactual_zero_y_origin_and_margin"]["rows_300dpi"] == 3508
print(json.dumps(result, indent=2))
