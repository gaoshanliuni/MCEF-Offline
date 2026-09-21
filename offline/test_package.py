#!/usr/bin/env python3
import io
from pathlib import Path
import tarfile
import tempfile
import unittest
import zipfile
from package import convert_native, manifest_bytes

class PackagingTests(unittest.TestCase):
    def test_roundtrip_and_symlinks(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            with tarfile.open(root/'native.tar.gz', 'w:gz') as tar:
                info = tarfile.TarInfo('linux_amd64/bin/lib.bin'); info.size = 3; info.mode = 0o755
                tar.addfile(info, io.BytesIO(b'abc'))
                link = tarfile.TarInfo('linux_amd64/current'); link.type = tarfile.SYMTYPE; link.linkname = 'bin/lib.bin'
                tar.addfile(link)
            result = convert_native(root/'native.tar.gz', 'linux_amd64', root/'runtime.zip', root/'runtime.properties')
            self.assertEqual(result['entryCount'], 2)
            with zipfile.ZipFile(root/'runtime.zip') as archive:
                self.assertEqual(archive.read('bin/lib.bin'), b'abc')
            self.assertIn('entry.0.executable=true', (root/'runtime.properties').read_text())
            self.assertIn('entry.1.type=link', (root/'runtime.properties').read_text())

    def test_traversal_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            with tarfile.open(root/'bad.tar.gz', 'w:gz') as tar:
                info = tarfile.TarInfo('linux_amd64/../outside'); info.size = 1
                tar.addfile(info, io.BytesIO(b'x'))
            with self.assertRaises(ValueError):
                convert_native(root/'bad.tar.gz', 'linux_amd64', root/'runtime.zip', root/'runtime.properties')

    def test_manifest_folding(self):
        out = manifest_bytes(b'Manifest-Version: 1.0\r\nLong: abc\r\n def\r\n\r\n', {'java-cef-commit': 'a'*40})
        self.assertIn(b'Long: abcdef\r\n', out)
        self.assertIn(b'java-cef-commit: '+b'a'*40+b'\r\n', out)

if __name__ == '__main__':
    unittest.main()
