#!/usr/bin/env python3
"""Run the supplied WIA DLL's command builder, without Windows or USB.

Requires lief and unicorn. Device parameters are synthetic; this probe does
not establish which parameters a complete Windows scanning session selects.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct

import lief
from unicorn import Uc, UC_ARCH_X86, UC_MODE_32, UC_HOOK_CODE
from unicorn.x86_const import UC_X86_REG_EAX, UC_X86_REG_ECX, UC_X86_REG_ESP

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("dll", type=Path)
args = parser.parse_args()
expected = "43a4bd4bf186a77f6a2328589085e0ef1c17870e3e0d691f1b1729a3f08231ff"
if hashlib.sha256(args.dll.read_bytes()).hexdigest() != expected:
    raise ValueError("DLL differs from analyzed build")
pe = lief.PE.parse(str(args.dll))
base = pe.optional_header.imagebase
cpu = Uc(UC_ARCH_X86, UC_MODE_32)
cpu.mem_map(base, (pe.optional_header.sizeof_image + 4095) & ~4095)
for section in pe.sections:
    cpu.mem_write(base + section.virtual_address, bytes(section.content))
cpu.mem_map(0x20000000, 0x10000)
cpu.mem_map(0x30000000, 0x1000)
cpu.mem_map(0x40000000, 0x10000)

def pack(*values):
    return struct.pack("<" + "I" * len(values), *values)

def string(address):
    return bytes(cpu.mem_read(address, 4096)).split(b"\0", 1)[0]

# Substitute only logging, registry lookup, cookie checking and lstrlenA.
# The original command builder, decimal formatting, and string helpers run.
cpu.mem_write(0x1c31f5e5, b"\xc3")
cpu.mem_write(0x1c3146aa, b"\x31\xc0\xc2\x08\x00")
cpu.mem_write(0x1c32219f, b"\xc3")
cpu.mem_write(0x1c30103c, pack(0x30000000))
cpu.mem_write(0x30000000, b"\xc2\x04\x00")

def hook(uc, address, size, user_data):
    if address == 0x30000000:
        stack = uc.reg_read(UC_X86_REG_ESP)
        pointer = struct.unpack("<I", uc.mem_read(stack + 4, 4))[0]
        uc.reg_write(UC_X86_REG_EAX, len(string(pointer)))
    elif address == 0x30000010:
        uc.emu_stop()

cpu.hook_add(UC_HOOK_CODE, hook)
obj, output, stack = 0x20000000, 0x20004000, 0x40008000
def call(address, parameters):
    cpu.mem_write(stack, pack(0x30000010, *parameters))
    cpu.reg_write(UC_X86_REG_ECX, obj)
    cpu.reg_write(UC_X86_REG_ESP, stack)
    cpu.emu_start(address, 0, count=100000)
    if cpu.reg_read(UC_X86_REG_ESP) != stack + 4 * (len(parameters) + 1):
        raise RuntimeError("Original routine did not return normally")


def parameter(kind, *values):
    block = 0x20006000
    cpu.mem_write(block, pack(kind, *values))
    call(0x1c31537f, [block])


parameter(1, 300, 300)  # Resolution
parameter(2, 0x208)  # Gray64
# BrMfcSetScanArea takes x, y, width, height, then calls DeviceSetParam.
# Its internal fields are left, right, top, bottom (not RECT order).
call(0x1c3141f1, [0, 0, 2480, 3506])
commands = {}
for name, compression in [("none", 0), ("rlength", 3)]:
    parameter(3, compression)
    cpu.mem_write(output, b"\0" * 4096)
    call(0x1c3168de, [output, 4096])
    command = string(output)
    assert command.startswith(b"\x1bX\nR=300,300\n")
    assert command.endswith(b"\x80")
    assert b"P=OFF" not in command
    assert b"A=0,0,2480,3506\n" in command
    assert (b"C=NONE\n" if compression == 0 else b"C=RLENGTH\n") in command
    commands[name] = command.decode("latin1")
print(json.dumps({"dll_sha256": expected,
                  "synthetic_rectangle_xywh": [0, 0, 2480, 3506],
                  "commands": commands}, indent=2))
