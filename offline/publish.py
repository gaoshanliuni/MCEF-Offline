#!/usr/bin/env python3
"""Publish a complete verified platform set, retaining the release ID from creation."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time
from package import REPOSITORY, commit, release_manifest

root = Path('build/release-assets')
if os.environ.get('GITHUB_REPOSITORY') != REPOSITORY or os.environ.get('GITHUB_REF') != 'refs/heads/main':
    raise RuntimeError('Publishing is restricted to trusted main')
release_manifest(root)
identity = json.loads((root/'mcef-offline-release.json').read_text())
tag = identity['tag']

def gh(*args, capture=False, payload=None):
    result = subprocess.run(['gh', *args], input=None if payload is None else json.dumps(payload),
                            check=True, text=True, stdout=subprocess.PIPE if capture else None)
    return result.stdout

api = f'repos/{REPOSITORY}/releases'
existing = json.loads(gh('api',api+'?per_page=100',capture=True))
for release in existing:
    if release['tag_name'] == tag:
        raise RuntimeError('Release exists; refusing overwrite. Rerun for a new run-attempt tag.')
body = ('# MCEF Offline 2.2.0 / NeoForge / Java 25\n\n'
    '从 Assets 选择与你的系统及 Java 架构一致的 **一个** `mcef-offline-neoforge-<platform>.jar`，替换原版 MCEF。不要同时安装多个 MCEF，也不要安装 api/sources 附件。\n\n'
    '提供 Windows x64、Linux x64、macOS Intel 和 Apple Silicon 四种包。固定上游的 Windows/Linux ARM64 包实际包含 x64 二进制，因此不作为原生 ARM64 发行。\n\n'
    '运行库在 JAR 内，首次本地安装、后续校验及损坏修复不请求网络。访问在线网页仍需网络。\n\n'
    '此发行基于 Minecraft 26.1.1 的 MCEF 2.2.0，用于 DivZero 26.1.2 兼容集成。\n\n'
    '验证范围：Java 编译、跨操作系统安装器单元测试、真实包内资源提取/复用/修复、PE/ELF/Mach-O 架构检查与 SHA-256。未替代真实游戏/浏览器渲染测试。\n\n'
    '开发者用 `mcef-offline-neoforge-api.jar` 编译，以 `mcef-offline-release.json` 锁定版本与哈希。完整对应源码在 `mcef-offline-corresponding-sources.jar`；许可证及第三方声明随附件提供。\n\n'
    f'Source: https://github.com/{REPOSITORY}/commit/{commit()}\n')
# Collection reads immediately after creation may be stale. The POST response
# already provides the exact draft ID, source commit and upload URL.
release = json.loads(gh('api','--method','POST',api,'--input','-',capture=True,payload={
    'tag_name':tag,'target_commitish':commit(),'name':f'MCEF Offline 2.2.0 — {commit()[:12]}',
    'body':body,'draft':True,'prerelease':True,'make_latest':'false'}))
if release['tag_name'] != tag or not release['draft'] or release['target_commitish'] != commit():
    raise RuntimeError('Created draft identity mismatch')
release_id = release['id']
files = sorted(p for p in root.iterdir() if p.is_file())
for file in files:
    gh('release','upload',tag,str(file),'--repo',REPOSITORY)
expected = {}
for file in files:
    with file.open('rb') as stream:
        digest = 'sha256:' + hashlib.file_digest(stream,'sha256').hexdigest()
    expected[file.name] = (file.stat().st_size,digest)
for attempt in range(5):
    release = json.loads(gh('api',f'{api}/{release_id}',capture=True))
    actual = {a['name']:(a['size'],a.get('digest')) for a in release['assets']}
    if len(release['assets']) == len(expected) and actual == expected:
        break
    if attempt == 4:
        raise RuntimeError('Uploaded asset set/size/SHA-256 verification failed')
    time.sleep(2*(attempt+1))
# Use the PATCH response directly, also avoiding a stale read immediately after publication.
release = json.loads(gh('api','--method','PATCH',f'{api}/{release_id}','--input','-',capture=True,
                       payload={'draft':False,'prerelease':True,'make_latest':'false'}))
if release['draft'] or not release['prerelease'] or release['tag_name'] != tag:
    raise RuntimeError('Release was not published as a prerelease')
url = release['html_url']
print('RELEASE_URL=' + url)
if os.environ.get('GITHUB_STEP_SUMMARY'):
    with open(os.environ['GITHUB_STEP_SUMMARY'],'a',encoding='utf-8') as summary:
        summary.write(f'## MCEF Offline\n[{tag}]({url})\nFour architecture-verified platform JARs plus pinned API, source and checksum assets.\n')
