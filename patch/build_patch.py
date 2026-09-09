#!/usr/bin/env python3
"""Build a version-locked C4 UI test package, never overwriting source binaries."""
from pathlib import Path
import hashlib
import json
import shutil
import struct
import subprocess
import sys
import argparse

ROOT = Path(__file__).resolve().parent.parent
SOURCE_SHA256 = "07af3e21bac5ba335d6d08317361e012c15a514b8d846a0a57508da46d282d0e"
ORIGINAL_SHA256 = SOURCE_SHA256
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--l2killer', action='store_true', help='Use the L2Killer C4 profile')
parser.add_argument('--source', type=Path, help='Path to the unmodified NWindow.dll')
options = parser.parse_args()
L2KILLER = options.l2killer
SOURCE_PATH = ROOT / 'NWindow.dll'
PACKAGE_NAME = 'C4Bars-teste-01'
if L2KILLER:
    SOURCE_SHA256 = '1fdcf9b455ef7ff93dfedeb9667e61a9874e31fe125982437d98c4d0adea3cce'
    SOURCE_PATH = ROOT / 'sources/NWindow-L2Killer.dll'
    PACKAGE_NAME = 'C4Bars-L2Killer-teste-05'
if options.source:
    SOURCE_PATH = options.source.expanduser().resolve()


def align(n, alignment):
    return (n + alignment - 1) // alignment * alignment


class PE:
    def __init__(self, data):
        self.data = bytearray(data)
        if self.data[:2] != b"MZ":
            raise ValueError("Not MZ")
        self.pe = self.u32(0x3c)
        if self.data[self.pe:self.pe + 4] != b"PE\0\0" or self.u16(self.pe + 4) != 0x14c:
            raise ValueError("Expected Windows x86 PE")
        self.opt = self.pe + 24
        if self.u16(self.opt) != 0x10b:
            raise ValueError("Expected PE32")
        self.table = self.opt + self.u16(self.pe + 20)
        self.sections = []
        for i in range(self.u16(self.pe + 6)):
            o = self.table + i * 40
            name = bytes(self.data[o:o + 8]).rstrip(b"\0").decode("ascii")
            virtual_size, rva, raw_size, raw = struct.unpack_from("<IIII", self.data, o + 8)
            self.sections.append((name, virtual_size, rva, raw_size, raw))

    def u16(self, o):
        return struct.unpack_from("<H", self.data, o)[0]

    def u32(self, o):
        return struct.unpack_from("<I", self.data, o)[0]

    def set32(self, o, value):
        struct.pack_into("<I", self.data, o, value)

    def directory(self, index):
        return struct.unpack_from("<II", self.data, self.opt + 96 + 8 * index)

    def offset(self, rva):
        if rva < self.u32(self.opt + 60):
            return rva
        for _, _, start, size, raw in self.sections:
            if start <= rva < start + size:
                return raw + rva - start
        raise ValueError(f"RVA {rva:x} has no file data")

    def cstring(self, rva):
        o = self.offset(rva)
        end = self.data.index(0, o)
        return bytes(self.data[o:end]).decode("ascii")

    def imports(self):
        rva, _ = self.directory(1)
        result = []
        if not rva:
            return result
        offset = self.offset(rva)
        while any(self.data[offset:offset + 20]):
            descriptor = list(struct.unpack_from("<IIIII", self.data, offset))
            result.append(descriptor)
            offset += 20
        return result


def checksum(data, checksum_offset):
    work = bytearray(data)
    work[checksum_offset:checksum_offset + 4] = b"\0" * 4
    if len(work) & 1:
        work.append(0)
    value = sum(word[0] for word in struct.iter_unpack("<H", work))
    value = (value & 0xffff) + (value >> 16)
    value = (value & 0xffff) + (value >> 16)
    return (value + len(data)) & 0xffffffff


def run(*args):
    subprocess.run([str(a) for a in args], check=True, cwd=ROOT)


def main():
    if not L2KILLER:
        raise SystemExit("This Auto Potion prototype requires --l2killer; its native RVAs do not support the original profile")
    source = SOURCE_PATH.read_bytes()
    if hashlib.sha256(source).hexdigest() != SOURCE_SHA256:
        raise SystemExit("NWindow.dll is not the analyzed version; refusing to patch")
    package = ROOT / "dist" / PACKAGE_NAME
    out = package / "bin"
    out.mkdir(parents=True, exist_ok=True)
    scratch = ROOT / "research" / "build"
    scratch.mkdir(parents=True, exist_ok=True)
    pe = PE(source)
    section_alignment, file_alignment = pe.u32(pe.opt + 32), pe.u32(pe.opt + 36)
    section_rva = align(max(rva + max(vsize, rawsize)
                           for _, vsize, rva, rawsize, _ in pe.sections), section_alignment)
    raw = align(len(source), file_alignment)
    old_imports = pe.imports()
    descriptor_bytes = (len(old_imports) + 2) * 20
    blob = bytearray(descriptor_bytes)

    def append(data, alignment=4):
        blob.extend(b"\0" * (align(len(blob), alignment) - len(blob)))
        rva = section_rva + len(blob)
        blob.extend(data)
        return rva

    name = append(b"C4Bars.dll\0")
    symbol = append(b"\0\0C4BarsInitialize\0", 2)
    lookup = append(struct.pack("<II", symbol, 0))
    iat = append(struct.pack("<II", symbol, 0))
    for i, desc in enumerate(old_imports):
        if desc[0] == 0:
            raise SystemExit("Missing original import lookup table; manual analysis required")
        desc[1] = 0  # invalidate any bound-import timestamp
        struct.pack_into("<IIIII", blob, i * 20, *desc)
    struct.pack_into("<IIIII", blob, len(old_imports) * 20, lookup, 0, 0, name, iat)
    old_entry = pe.u32(pe.opt + 16)
    run("i686-w64-mingw32-gcc", "-c", "patch/entry.S",
        f"-DORIGINAL_ENTRY_RVA={old_entry}", f"-DINIT_IAT_RVA={iat}", "-o", scratch / "entry.o")
    run("i686-w64-mingw32-objcopy", "-O", "binary", "--only-section=.text",
        scratch / "entry.o", scratch / "entry.bin")
    imports_size = len(blob)
    entry = append((scratch / "entry.bin").read_bytes(), section_alignment)
    code_offset = entry - section_rva
    code_size = len(blob) - code_offset
    header_offset = pe.table + len(pe.sections) * 40
    if header_offset + 80 > pe.u32(pe.opt + 60) or any(pe.data[header_offset:header_offset + 80]):
        raise SystemExit("No free PE section header")
    raw_size = align(len(blob), file_alignment)
    pe.data.extend(b"\0" * (raw - len(pe.data)))
    pe.data.extend(blob)
    pe.data.extend(b"\0" * (raw_size - len(blob)))
    struct.pack_into("<8sIIIIIIHHI", pe.data, header_offset,
                     b".c4imp\0", imports_size, section_rva, code_offset, raw, 0, 0, 0, 0, 0xc0000040)
    struct.pack_into("<8sIIIIIIHHI", pe.data, header_offset + 40,
                     b".c4code\0", code_size, entry, raw_size - code_offset,
                     raw + code_offset, 0, 0, 0, 0, 0x60000020)
    struct.pack_into("<H", pe.data, pe.pe + 6, len(pe.sections) + 2)
    pe.set32(pe.opt + 4, pe.u32(pe.opt + 4) + raw_size - code_offset)
    pe.set32(pe.opt + 8, pe.u32(pe.opt + 8) + code_offset)
    pe.set32(pe.opt + 16, entry)
    pe.set32(pe.opt + 56, align(section_rva + len(blob), section_alignment))
    struct.pack_into("<II", pe.data, pe.opt + 96 + 8, section_rva, descriptor_bytes)
    # Certificate and bound-import metadata no longer describe the edited file.
    # Preserve the original IAT directory so Windows unprotects its original
    # thunk pages. The added IAT is in a separate writable, non-executable
    # section; entry code is in a separate read/execute section.
    for index in (4, 11):
        struct.pack_into("<II", pe.data, pe.opt + 96 + index * 8, 0, 0)
    pe.set32(pe.opt + 64, checksum(pe.data, pe.opt + 64))
    (out / "NWindow.dll").write_bytes(pe.data)
    run("i686-w64-mingw32-g++", "-shared", "-Os", "-std=c++17", "-Wall", "-Wextra", "-Werror",
        "-fno-exceptions", "-fno-rtti", "-fno-builtin", "-fno-stack-protector", "-nostdlib",
        *(['-DC4BARS_L2KILLER'] if L2KILLER else []),
        *(['-Wl,--image-base,0x68840000'] if L2KILLER else []),
        "patch/C4Bars.cpp", "-Wl,--entry,_DllMain@12", "-Wl,--kill-at", "-Wl,--no-insert-timestamp",
        "-lkernel32", "-luser32", "-o", out / "C4Bars.dll")
    for path in (ROOT / "patch" / "package").iterdir():
        if path.is_file():
            shutil.copy2(path, package / path.name)
    if L2KILLER:
        readme = package / 'LEIA-ME.txt'
        readme.write_text(readme.read_text().replace('C4Bars - teste 01', 'C4Bars - L2Killer teste 05')
                         .replace('C4Bars-teste-01', PACKAGE_NAME), encoding='utf-8')
    manifest = {
        "version": "l2killer-test-05" if L2KILLER else "test-01", "original_sha256": SOURCE_SHA256,
        "patched_sha256": hashlib.sha256(pe.data).hexdigest(),
        "dll_sha256": hashlib.sha256((out / "C4Bars.dll").read_bytes()).hexdigest(),
        "original_entry_rva": hex(old_entry), "entry_rva": hex(entry),
        "init_iat_rva": hex(iat), "section_rva": hex(section_rva),
        "status": "Experimental; game runtime validation pending",
    }
    manager = package / "Gerenciar.ps1"
    manager.write_text(manager.read_text().replace("__PATCH_SHA256__", manifest["patched_sha256"])
                       .replace("__DLL_SHA256__", manifest["dll_sha256"])
                       .replace(ORIGINAL_SHA256, SOURCE_SHA256)
                       .replace('C4Bars-teste-01', PACKAGE_NAME), encoding="utf-8")
    (package / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
