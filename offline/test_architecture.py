import struct
import unittest
from native_architecture import binary_architectures

class ArchitectureTests(unittest.TestCase):
    def test_machine_types(self):
        pe=bytearray(128);pe[:2]=b'MZ';struct.pack_into('<I',pe,0x3c,64);pe[64:68]=b'PE\0\0'
        struct.pack_into('<H',pe,68,0x8664)
        self.assertEqual(binary_architectures(pe),{'amd64'})
        struct.pack_into('<H',pe,68,0xaa64)
        self.assertEqual(binary_architectures(pe),{'arm64'})
        elf=bytearray(64);elf[:4]=b'\x7fELF';elf[4]=2;elf[5]=1
        struct.pack_into('<H',elf,18,62)
        self.assertEqual(binary_architectures(elf),{'amd64'})
        struct.pack_into('<H',elf,18,183)
        self.assertEqual(binary_architectures(elf),{'arm64'})
        self.assertEqual(binary_architectures(b'\xcf\xfa\xed\xfe'+struct.pack('<I',0x0100000c)),{'arm64'})
        with self.assertRaises(ValueError):binary_architectures(b'not executable')

if __name__=='__main__':unittest.main()
