#!/usr/bin/env python3
"""Build-time packaging only. The Java runtime installer never uses this downloader."""
from __future__ import annotations
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import posixpath
import re
import shutil
import subprocess
import tarfile
import time
import urllib.request
import zipfile
from native_architecture import binary_architectures, verify_native_architecture

ROOT = Path(__file__).resolve().parent.parent
# The pinned upstream Windows/Linux ARM64 archives contain x64 binaries.
# Never advertise those archives as native ARM64 builds.
PLATFORMS = ('windows_amd64', 'linux_amd64', 'macos_amd64', 'macos_arm64')
JCEF = 'eaeb3d4370aa3526ee237ad1981ad59af3de4dd1'
UPSTREAM = 'e2a48d91ab08b5f5898ba440dbb69e57b6355615'
REPOSITORY = 'gaoshanliuni/MCEF-Offline'
MAX_NATIVE = 2 * 1024**3
MAX_EXPANDED = 4 * 1024**3


def sha(path: Path) -> str:
    with path.open('rb') as handle:
        return hashlib.file_digest(handle, 'sha256').hexdigest()


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def record(path: Path) -> dict:
    return {'file': path.name, 'sha256': sha(path), 'size': path.stat().st_size}


def commit() -> str:
    value = os.environ.get('GITHUB_SHA') or subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    if not re.fullmatch('[a-f0-9]{40}', value):
        raise ValueError('Source commit must be an exact Git SHA')
    return value


def fetch(url: str, destination: Path, limit: int) -> None:
    if not url.startswith('https://mcef-download.cinemamod.com/java-cef-builds/' + JCEF + '/'):
        raise ValueError('Unexpected native download origin')
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'MCEF-Offline release builder'})
            with urllib.request.urlopen(req, timeout=60) as response, destination.open('wb') as out:
                if response.status != 200:
                    raise OSError('Unexpected native download status')
                count = 0
                while chunk := response.read(256 * 1024):
                    count += len(chunk)
                    if count > limit:
                        raise ValueError('Native download exceeds size limit')
                    out.write(chunk)
            return
        except OSError:
            if attempt == 2:
                raise
            time.sleep(2 ** attempt)


def encoded(value: str) -> str:
    return base64.urlsafe_b64encode(value.encode('utf-8')).decode('ascii').rstrip('=')


def clean_path(name: str, platform: str) -> str:
    while name.startswith('./'):
        name = name[2:]
    if name == platform or name == platform + '/':
        return ''
    if not name.startswith(platform + '/'):
        raise ValueError('Native archive entry is outside its platform directory: ' + name)
    name = name[len(platform) + 1:].rstrip('/')
    if not name or name.startswith('/') or '\\' in name or ':' in name or '\0' in name:
        raise ValueError('Unsafe native archive path')
    if any(part in ('', '.', '..') for part in name.split('/')):
        raise ValueError('Unsafe native archive path segment')
    if name == '.complete':
        raise ValueError('Reserved native archive entry')
    return name


def convert_native(native: Path, platform: str, out_zip: Path, properties: Path) -> dict:
    """Preserve macOS symlinks and executable modes without extracting a TAR on the builder."""
    entries: list[dict] = []
    seen: set[str] = set()
    total = 0
    with tarfile.open(native, 'r:gz') as tar, zipfile.ZipFile(out_zip, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6, allowZip64=True) as packed:
        for item in tar:
            name = clean_path(item.name, platform)
            if item.isdir() or not name:
                continue
            if name in seen:
                raise ValueError('Duplicate native archive entry: ' + name)
            seen.add(name)
            if item.issym():
                target = item.linkname
                resolved = posixpath.normpath(posixpath.join(posixpath.dirname(name), target))
                if not target or target.startswith('/') or '\\' in target or ':' in target or resolved == '..' or resolved.startswith('../'):
                    raise ValueError('Native symbolic link escapes the bundle')
                entries.append({'path': encoded(name), 'type': 'link', 'target': encoded(target)})
                continue
            if not (item.isfile() or item.islnk()):
                raise ValueError('Unsupported native archive entry type')
            if item.islnk():
                clean_path(item.linkname, platform)
            digest = hashlib.sha256()
            size = 0
            mode = 0o100755 if item.mode & 0o111 else 0o100644
            info = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = mode << 16
            source = tar.extractfile(item)
            if source is None:
                raise ValueError('Missing native file data')
            with source, packed.open(info, 'w', force_zip64=True) as destination:
                while chunk := source.read(256 * 1024):
                    size += len(chunk)
                    total += len(chunk)
                    if total > MAX_EXPANDED:
                        raise ValueError('Native archive expansion exceeds size limit')
                    digest.update(chunk)
                    destination.write(chunk)
            entries.append({'path': encoded(name), 'type': 'file', 'sha256': digest.hexdigest(), 'size': str(size), 'executable': str(bool(item.mode & 0o111)).lower()})
    if not entries or len(entries) > 50_000:
        raise ValueError('Invalid native archive entry count')
    for name in seen:
        for parent in PurePosixPath(name).parents:
            if str(parent) != '.' and str(parent) in seen:
                raise ValueError('Native file or link is used as a parent directory')
    fields = {'format': '1', 'platform': platform, 'commit': JCEF, 'archive.sha256': sha(out_zip), 'archive.size': str(out_zip.stat().st_size), 'entry.count': str(len(entries))}
    for index, entry in enumerate(entries):
        fields.update({f'entry.{index}.{key}': value for key, value in entry.items()})
    properties.write_text(''.join(f'{key}={value}\n' for key, value in fields.items()), encoding='ascii')
    return {'archiveSha256': fields['archive.sha256'], 'entryCount': len(entries), 'expandedBytes': total, 'paths': sorted(seen)}


def manifest_bytes(raw: bytes, attributes: dict[str, str]) -> bytes:
    lines = raw.decode('utf-8').replace('\r\n', '\n').split('\n')
    values: dict[str, str] = {}
    key: str | None = None
    for line in lines:
        if not line:
            break
        if line.startswith(' ') and key:
            values[key] += line[1:]
        else:
            key, value = line.split(': ', 1)
            values[key] = value
    values.update(attributes)
    out = bytearray()
    for key, value in values.items():
        line = (key + ': ' + value).encode('utf-8')
        while len(line) > 70:
            out.extend(line[:70] + b'\r\n')
            line = b' ' + line[70:]
        out.extend(line + b'\r\n')
    return bytes(out) + b'\r\n'


def copy_jar(source: Path, output: Path, attrs: dict[str, str], additions: dict[str, Path | bytes]) -> None:
    with zipfile.ZipFile(source) as inp, zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED, allowZip64=True) as out:
        seen = set()
        for entry in inp.infolist():
            if entry.filename in seen or entry.filename in additions:
                raise ValueError('Duplicate JAR resource')
            seen.add(entry.filename)
            if re.match(r'META-INF/[^/]+\.(SF|RSA|DSA)$', entry.filename, re.I):
                raise ValueError('Refusing to modify a signed JAR')
            if entry.filename == 'META-INF/MANIFEST.MF':
                out.writestr(entry, manifest_bytes(inp.read(entry), attrs))
            else:
                with inp.open(entry) as src, out.open(entry, 'w', force_zip64=True) as dest:
                    shutil.copyfileobj(src, dest, length=256 * 1024)
        if 'META-INF/MANIFEST.MF' not in seen:
            raise ValueError('Missing JAR manifest')
        for name, data in additions.items():
            if isinstance(data, bytes):
                out.writestr(name, data)
            else:
                out.write(data, name, compress_type=zipfile.ZIP_STORED if name.endswith('.zip') else zipfile.ZIP_DEFLATED)


def make_base(input_dir: Path, output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    jars = [p for p in input_dir.glob('*.jar') if not re.search(r'(sources|javadoc)', p.name)]
    all_jars = [p for p in jars if p.name.endswith('-all.jar')]
    if all_jars:
        jars = all_jars
    if len(jars) != 1:
        raise ValueError('Expected one production NeoForge JAR, got: ' + repr(jars))
    with zipfile.ZipFile(jars[0]) as jar:
        for required in ('META-INF/neoforge.mods.toml', 'com/cinemamod/mcef/offline/OfflineRuntime.class', 'com/cinemamod/mcef/mixins/MixinClientPackSource.class'):
            if required not in jar.namelist():
                raise ValueError('Required offline class/resource missing: ' + required)
        mixin = jar.read('com/cinemamod/mcef/mixins/MixinClientPackSource.class')
        if b'MCEFDownloader' in mixin or b'OfflineRuntime' not in mixin:
            raise ValueError('Network-based initialization has not been replaced')
    identity = {'schema': 1, 'repository': REPOSITORY, 'sourceCommit': commit(), 'upstreamCommit': UPSTREAM, 'jcefCommit': JCEF,
                'mcefVersion': '2.2.0', 'minecraftVersion': '26.1.1', 'requiredJava': 25, 'platforms': list(PLATFORMS),
                'acceptance': 'Compiled fork plus standalone installation/repair tests; not in-game/browser rendering acceptance.'}
    api = output / 'mcef-offline-neoforge-api.jar'
    copy_jar(jars[0], api, {'java-cef-commit': JCEF, 'MCEF-Offline-Source': commit(), 'MCEF-Offline-Distribution': 'compile-only'},
             {'mcef-offline/BUILD.json': json.dumps(identity, indent=2).encode('utf-8'),
              'mcef-offline/licenses/JCEF-LICENSE.txt': ROOT / 'common/java-cef/LICENSE.txt',
              'mcef-offline/licenses/MCEF-LICENSE.txt': ROOT / 'LICENSE'})
    sources = output / 'mcef-offline-corresponding-sources.jar'
    with zipfile.ZipFile(sources, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        paths = subprocess.check_output(['git', 'ls-files', '-z'], cwd=ROOT).decode().split('\0')
        for name in paths:
            path = ROOT / name
            if name and path.is_file() and not path.is_symlink():
                archive.write(path, name)
        jcef_paths = subprocess.check_output(['git', 'ls-files', '-z'], cwd=ROOT / 'common/java-cef').decode().split('\0')
        for name in jcef_paths:
            path = ROOT / 'common/java-cef' / name
            if name and path.is_file() and not path.is_symlink():
                archive.write(path, 'common/java-cef/' + name)
    shutil.copyfile(ROOT / 'LICENSE', output / 'LICENSE-MCEF.txt')
    shutil.copyfile(ROOT / 'offline/THIRD_PARTY_NOTICES.md', output / 'MCEF-OFFLINE-NOTICES.md')
    identity.update({'api': record(api), 'sources': record(sources)})
    write_json(output / 'MCEF-OFFLINE-BUILD.json', identity)


def make_platform(base: Path, platform: str, output: Path) -> None:
    if platform not in PLATFORMS:
        raise ValueError('Unsupported platform; see offline/UNSUPPORTED_PLATFORMS.md')
    output.mkdir(parents=True, exist_ok=True)
    cache = ROOT / 'build/native-inputs' / platform
    cache.mkdir(parents=True, exist_ok=True)
    url = f'https://mcef-download.cinemamod.com/java-cef-builds/{JCEF}/{platform}.tar.gz'
    checksum = cache / 'upstream.sha256'
    fetch(url + '.sha256', checksum, 1024 * 1024)
    expected = set(re.findall(r'(?<![a-fA-F0-9])[a-fA-F0-9]{64}(?![a-fA-F0-9])', checksum.read_text(encoding='utf-8-sig')))
    if len(expected) != 1:
        raise ValueError('Upstream checksum must contain exactly one SHA-256 value')
    expected_hash = expected.pop().lower()
    native = cache / (platform + '.tar.gz')
    if not native.is_file() or sha(native) != expected_hash:
        fetch(url, native, MAX_NATIVE)
    if sha(native) != expected_hash:
        raise ValueError('Upstream native archive SHA-256 mismatch')
    bundle, props = cache / 'runtime.zip', cache / 'runtime.properties'
    metadata = convert_native(native, platform, bundle, props)
    metadata.pop('paths')
    required = ('jcef.dll', 'libcef.dll') if platform.startswith('windows') else ('libjcef.so', 'libcef.so') if platform.startswith('linux') else ('libjcef.dylib', 'Chromium Embedded Framework')
    metadata['nativeArchitectures'] = verify_native_architecture(bundle, platform, required)
    prefix = f'mcef-offline/{platform}/'
    artifact = output / f'mcef-offline-neoforge-{platform}.jar'
    copy_jar(base, artifact, {'MCEF-Offline-Distribution': platform}, {prefix+'runtime.zip': bundle, prefix+'runtime.properties': props,
             prefix+'upstream.sha256': checksum})
    metadata.update(record(artifact))
    metadata.update({'platform': platform, 'jcefCommit': JCEF, 'nativeUpstream': url, 'nativeUpstreamSha256': expected_hash})
    write_json(output / f'MCEF-OFFLINE-{platform}.json', metadata)


def release_manifest(directory: Path) -> None:
    identity = json.loads((directory / 'MCEF-OFFLINE-BUILD.json').read_text())
    if identity['sourceCommit'] != commit():
        raise ValueError('Build source identity mismatch')
    platforms = {}
    for platform in PLATFORMS:
        item = json.loads((directory / f'MCEF-OFFLINE-{platform}.json').read_text())
        if item['jcefCommit'] != JCEF or item['platform'] != platform or record(directory / item['file']) != {key:item[key] for key in ('file','sha256','size')}:
            raise ValueError('Platform artifact identity mismatch')
        expected_cpu = platform.rsplit('_',1)[1]
        if not item.get('nativeArchitectures') or any(expected_cpu not in values for values in item['nativeArchitectures'].values()):
            raise ValueError('Missing/mismatched native architecture attestation')
        platforms[platform] = item
    for key in ('api', 'sources'):
        if record(directory / identity[key]['file']) != identity[key]:
            raise ValueError('Base artifact identity mismatch')
    identity['platforms'] = platforms
    run = os.environ.get('GITHUB_RUN_ID', '0')
    attempt = os.environ.get('GITHUB_RUN_ATTEMPT', '0')
    if not run.isdigit() or not attempt.isdigit():
        raise ValueError('Invalid release run identity')
    identity['tag'] = f'offline-2.2.0-{commit()[:12]}-r{run}-a{attempt}'
    write_json(directory / 'mcef-offline-release.json', identity)
    checksums = [f'{sha(file)}  {file.name}\n' for file in sorted(directory.iterdir()) if file.is_file() and file.name != 'SHA256SUMS']
    (directory / 'SHA256SUMS').write_text(''.join(checksums), encoding='ascii')
    if os.environ.get('GITHUB_OUTPUT'):
        with open(os.environ['GITHUB_OUTPUT'], 'a', encoding='utf-8') as output:
            output.write('tag=' + identity['tag'] + '\n')


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest='command', required=True)
    base = sub.add_parser('base')
    base.add_argument('--input', type=Path, default=ROOT / 'neoforge/build/libs')
    base.add_argument('--output', type=Path, default=ROOT / 'build/offline-base')
    platform = sub.add_parser('platform')
    platform.add_argument('--base', type=Path, required=True)
    platform.add_argument('--platform', choices=PLATFORMS, required=True)
    platform.add_argument('--output', type=Path, default=ROOT / 'build/offline-platform')
    release = sub.add_parser('release')
    release.add_argument('--directory', type=Path, required=True)
    args = parser.parse_args()
    if args.command == 'base':
        make_base(args.input, args.output)
    elif args.command == 'platform':
        make_platform(args.base, args.platform, args.output)
    else:
        release_manifest(args.directory)

if __name__ == '__main__':
    main()
