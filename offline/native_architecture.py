#!/usr/bin/env python3
"""Build-time PE/ELF/Mach-O validation. Archive names are not evidence of CPU architecture."""
from pathlib import Path, PurePosixPath
import struct
import zipfile


def binary_architectures(data: bytes) -> set[str]:
    if data[:2] == b'MZ' and len(data) >= 64:
        offset = struct.unpack_from('<I', data, 0x3c)[0]
        if offset + 6 > len(data) or data[offset:offset+4] != b'PE\x00\x00':
            raise ValueError('Invalid PE header')
        machine = struct.unpack_from('<H', data, offset+4)[0]
        return {0x8664: {'amd64'}, 0xaa64: {'arm64'}}.get(machine, set())
    if data[:4] == b'\x7fELF' and len(data) >= 20:
        if data[4] != 2 or data[5] not in (1, 2):
            raise ValueError('Unsupported ELF class/byte order')
        machine = struct.unpack_from('<H' if data[5] == 1 else '>H', data, 18)[0]
        return {62: {'amd64'}, 183: {'arm64'}}.get(machine, set())
    magic = bytes(data[:4])
    thin = {b'\xcf\xfa\xed\xfe': '<', b'\xfe\xed\xfa\xcf': '>'}
    cpus = {0x01000007: 'amd64', 0x0100000c: 'arm64'}
    if magic in thin and len(data) >= 8:
        cpu = struct.unpack_from(thin[magic]+'I', data, 4)[0]
        return {cpus[cpu]} if cpu in cpus else set()
    fat = {b'\xca\xfe\xba\xbe': ('>', 20), b'\xbe\xba\xfe\xca': ('<', 20),
           b'\xca\xfe\xba\xbf': ('>', 32), b'\xbf\xba\xfe\xca': ('<', 32)}
    if magic in fat and len(data) >= 8:
        endian, stride = fat[magic]
        count = struct.unpack_from(endian+'I', data, 4)[0]
        if not 1 <= count <= 32 or 8+stride*count > len(data):
            raise ValueError('Invalid universal Mach-O header')
        return {cpus[cpu] for i in range(count) if (cpu := struct.unpack_from(endian+'I', data, 8+i*stride)[0]) in cpus}
    raise ValueError('Unrecognized native executable format')


def verify_native_architecture(bundle: Path, platform: str, required: tuple[str, ...]) -> dict:
    expected = platform.rsplit('_', 1)[1]
    result = {}
    with zipfile.ZipFile(bundle) as archive:
        for name in required:
            paths = [p for p in archive.namelist() if PurePosixPath(p).name == name]
            if not paths:
                raise ValueError('Essential native library has no regular-file entry: ' + name)
            for path in paths:
                with archive.open(path) as handle:
                    actual = binary_architectures(handle.read(1024*1024))
                if expected not in actual:
                    raise ValueError(f'Native architecture mismatch: {platform}, {path}, actual={sorted(actual)}')
                result[path] = sorted(actual)
    return result
