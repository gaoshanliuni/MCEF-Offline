# MCEF Offline

按平台发布、自带 Chromium/JCEF 运行库的 MCEF 分支。首次启动从 JAR 内提取，后续验证本地缓存；文件损坏时从 JAR 内修复。**运行库初始化不访问下载站、不请求远端校验文件、不回退在线下载。**

## 安装

从本仓库 **Releases → Assets** 选择与你运行 Minecraft 的 Java 架构一致的 **一个**附件：

| 平台 | 安装文件 |
| --- | --- |
| Windows x64 | `mcef-offline-neoforge-windows_amd64.jar` |
| Windows ARM64 | `mcef-offline-neoforge-windows_arm64.jar` |
| Linux x64 | `mcef-offline-neoforge-linux_amd64.jar` |
| Linux ARM64 | `mcef-offline-neoforge-linux_arm64.jar` |
| macOS Intel | `mcef-offline-neoforge-macos_amd64.jar` |
| macOS Apple Silicon | `mcef-offline-neoforge-macos_arm64.jar` |

放入客户端 `mods`，移除原版 MCEF 或其它平台的 MCEF JAR。保留主模组及 WebGUI。不要把 `api`、`sources` 或 GitHub 自动生成的 Source code 附件放入 mods。此分支保持 `mod_id=mcef`，不能与原版一起安装。

此兼容基线是 **MCEF 2.2.0、Minecraft 26.1.1、NeoForge、Java 25**，用于 DivZero 已锁定的 26.1.2 集成环境；不是对其它 Minecraft/加载器版本的兼容承诺。平台产物构建成功不等于已在该硬件上完成游戏内渲染验收。浏览在线网页、访问 AI API 仍需联网；此处的离线指浏览器运行库的安装和修复。

## 构建与来源

上游旧地址 Keksuccino/mcef 已迁移到 `Keksuccino/Rinku`。本仓库导入 `26.1.1-legacy` 对应源码快照，不跟随 Rinku 新版 API：

- MCEF source: `e2a48d91ab08b5f5898ba440dbb69e57b6355615`
- JCEF source/native build: `eaeb3d4370aa3526ee237ad1981ad59af3de4dd1`

```sh
git clone --recurse-submodules https://github.com/gaoshanliuni/MCEF-Offline.git
cd MCEF-Offline
python offline/test.py
python offline/test_package.py
./gradlew :neoforge:jarJar :neoforge:sourcesJar --no-daemon
python offline/package.py base
python offline/package.py platform --base build/offline-base/mcef-offline-neoforge-api.jar --platform windows_amd64
```

Windows 使用 `gradlew.bat`。需要 Java 25、Python 3.11+。开发者/CI 构建时会下载 Gradle、Minecraft 依赖和固定 JCEF 运行库；**玩家启动时不会下载运行库**。

自动化流程先编译一个公共 API 基底，再为六个平台分别打包，验证 SHA-256，全部通过后发布独立 JAR 附件、完整对应源码、许可证及 `mcef-offline-release.json`。发行标签含源码提交和工作流执行号，已发布版本不覆盖。只有成功发布的附件才算构建产物；不要把源代码仓库视为已经通过游戏验收。

## 下游编译接入

消费本仓库某个固定 Release 的 `mcef-offline-neoforge-api.jar` 编译，并锁定其 SHA-256。运行/发行阶段选择同一 Release 的平台 JAR。版本与哈希保存在下游仓库锁文件中，**不要依赖 latest 或浮动 main**。`mcef-offline-release.json` 包含每个平台和源码附件的哈希、大小、固定 JCEF 构建及源提交，可用于 DivZero 自动发版增加离线附件。

## 缓存与修复

缓存位于实例工作目录 `mods/mcef-libraries/offline/<jcef-commit>/<platform>/`。安装过程使用进程锁、临时目录、压缩包与逐文件 SHA-256 校验，成功后才切换当前版本指针；不覆盖其它进程可能正在加载的 DLL。保留 macOS 符号链接、Unix 可执行权限，拒绝路径穿越和未知条目。旧缓存不会自动删除；关闭全部游戏进程后可手动清理该专用缓存目录。

测试覆盖首次提取、缓存复用、损坏修复、中断/错误压缩包、版本不匹配、并发安装、目录符号链接与权限。完整游戏验收还需在已装好游戏依赖的测试实例中断网启动，验证本地网页渲染。

许可：LGPL-2.1-or-later。详见 `LICENSE`、`offline/THIRD_PARTY_NOTICES.md`，发行附件提供对应源码。离线打包不解决旧版 Chromium 自身的安全问题。
