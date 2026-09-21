#!/usr/bin/env python3
"""Publish this run's verified platform set. Never replace an existing published release."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
from package import REPOSITORY, commit, release_manifest

root = Path('build/release-assets')
if os.environ.get('GITHUB_REPOSITORY') != REPOSITORY or os.environ.get('GITHUB_REF') != 'refs/heads/main':
    raise RuntimeError('Publishing is restricted to trusted main')
release_manifest(root)
identity = json.loads((root/'mcef-offline-release.json').read_text())
tag = identity['tag']

def gh(*args, capture=False):
    result = subprocess.run(['gh', *args], check=True, text=True, stdout=subprocess.PIPE if capture else None)
    return result.stdout

# A draft without a Git tag is absent from GET /releases/tags/{tag}; list drafts
# through the authenticated releases collection and retain the numeric release id.
def releases():
    return json.loads(gh('api',f'repos/{REPOSITORY}/releases?per_page=100',capture=True))

for release in releases():
    # Remove only our known failed initial draft containing mislabeled ARM64 artifacts.
    if (release['tag_name']=='offline-2.2.0-3a8b37533af9-r35622948459-a1'
            and release['draft'] and release['target_commitish']=='3a8b37533af9d210b9d1d6381d44d4e5e8655437'):
        gh('api','--method','DELETE',f"repos/{REPOSITORY}/releases/{release['id']}")
    if release['tag_name']==tag:
        raise RuntimeError('Release exists; refusing overwrite. Rerun for a new run-attempt tag.')
notes = Path('build/offline-release-notes.md')
notes.write_text('# MCEF Offline 2.2.0 / NeoForge / Java 25\n\n'
    '从 Assets 选择与你的系统及 Java 架构一致的 **一个** `mcef-offline-neoforge-<platform>.jar`，替换原版 MCEF。不要同时安装多个 MCEF，也不要安装 api/sources 附件。\n\n'
    '提供 Windows x64、Linux x64、macOS Intel 和 Apple Silicon 四种包。固定上游的 Windows/Linux ARM64 压缩包实际包含 x64 二进制，因此不作为原生 ARM64 发行。\n\n'
    '运行库在 JAR 内，首次本地安装、后续校验及损坏修复不请求网络。访问在线网页仍需网络。\n\n'
    '此发行基于 Minecraft 26.1.1 的 MCEF 2.2.0，用于 DivZero 26.1.2 兼容集成。\n\n'
    '验证范围：Java 编译、安装器跨操作系统单元测试、真实包内资源的提取/复用/损坏修复、PE/ELF/Mach-O 架构检查与 SHA-256。未替代真实游戏/浏览器渲染测试。\n\n'
    '开发者用 `mcef-offline-neoforge-api.jar` 编译，以 `mcef-offline-release.json` 锁定版本与哈希。完整对应源码在 `mcef-offline-corresponding-sources.jar`；许可证及第三方声明随附件提供。\n\n'
    f'Source: https://github.com/{REPOSITORY}/commit/{commit()}\n', encoding='utf-8')
gh('release','create',tag,'--repo',REPOSITORY,'--target',commit(),'--draft','--prerelease','--title',f'MCEF Offline 2.2.0 — {commit()[:12]}','--notes-file',str(notes))
matches=[r for r in releases() if r['tag_name']==tag]
if len(matches)!=1 or not matches[0]['draft'] or matches[0]['target_commitish']!=commit():
    raise RuntimeError('Draft release identity mismatch')
release_id=matches[0]['id']
files = sorted(p for p in root.iterdir() if p.is_file())
for file in files:
    gh('release','upload',tag,str(file),'--repo',REPOSITORY)
release=json.loads(gh('api',f'repos/{REPOSITORY}/releases/{release_id}',capture=True))
assets = release['assets']
if len(assets) != len(files):
    raise RuntimeError('Uploaded asset set is incomplete')
for file in files:
    matches = [a for a in assets if a['name'] == file.name]
    with file.open('rb') as stream:
        expected = 'sha256:' + hashlib.file_digest(stream,'sha256').hexdigest()
    if len(matches) != 1 or matches[0]['size'] != file.stat().st_size or matches[0].get('digest') != expected:
        raise RuntimeError('Uploaded asset identity mismatch: ' + file.name)
gh('release','edit',tag,'--repo',REPOSITORY,'--draft=false','--prerelease','--latest=false')
release=json.loads(gh('api',f'repos/{REPOSITORY}/releases/{release_id}',capture=True))
if release['draft'] or not release['prerelease']:
    raise RuntimeError('Release was not published as a prerelease')
url=release['html_url']
print('RELEASE_URL=' + url)
if os.environ.get('GITHUB_STEP_SUMMARY'):
    with open(os.environ['GITHUB_STEP_SUMMARY'],'a',encoding='utf-8') as summary:
        summary.write(f'## MCEF Offline\n[{tag}]({url})\nFour architecture-verified platform JARs plus pinned API, source and checksum assets.\n')
