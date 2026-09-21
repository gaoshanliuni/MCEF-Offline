# Native architecture verification

For pinned JCEF build `eaeb3d4370aa3526ee237ad1981ad59af3de4dd1`, the initial CI artifacts were inspected before publication on 2026-09-21.

- The upstream `windows_arm64.tar.gz` archive (SHA-256 `7710781d35b6d5ae7052de1126cbd21e872f33aebb653829c1491ab156d196be`) contains `jcef.dll` and `libcef.dll` with PE machine **0x8664 (x86-64)**, not 0xAA64 (ARM64).
- The upstream `linux_arm64.tar.gz` archive (SHA-256 `ae3e28e912ac30931a8b6522b28c90d9af58bcb61130103ad7987989b9d7c495`) contains `libjcef.so` and `libcef.so` with ELF `e_machine=62` (x86-64), not 183 (AArch64).

Consequently this release does NOT publish native Windows ARM64 or Linux ARM64 packages. Renaming an archive is not architecture support. Re-enable either target only after a matching, verified JCEF/CEF build exists and passes installation and native execution tests. An x64 JVM on an emulated system is a separate deployment path and is not validated here.

Release packaging parses PE, ELF and Mach-O headers of both essential JCEF/CEF libraries, checks the requested CPU architecture, and records the result in each platform's metadata. Supported release targets are Windows x64, Linux x64, macOS Intel and macOS Apple Silicon. A passing header/installation check is not a claim of in-game rendering acceptance.
