# MCEF Offline

自带 Chromium/JCEF 运行库的 MCEF 分支。首次启动从 JAR 内提取，后续验证本地缓存；文件损坏时从 JAR 内修复。**运行库初始化不访问下载站、不请求远端校验文件、不回退在线下载。**

## 安装

从本仓库 Releases → Assets 选择与你运行 Minecraft 的 Java 架构一致的 **一个**附件：

| 平台 | 安装文件 |
| --- | --- |
| Windows x64 | `mcef-offline-neoforge-windows_amd64.jar` |
| Linux x64 | `mcef-offline-neoforge-linux_amd64.jar` |
| macOS Intel | `mcef-offline-neoforge-macos_amd64.jar` |
| macOS Apple Silicon | `mcef-offline-neoforge-macos_arm64.jar` |

**不发布原生 Windows ARM64/Linux ARM64 包**：固定上游中这两个名称的包实际是 x64 二进制。详见 `offline/UNSUPPORTED_PLATFORMS.md`。不能把重命名当作架构支持。

将一个平台 JAR 放入客户端 mods，移除原版或其它平台的 MCEF。保留主模组及 WebGUI。不要安装 api、sources 或 GitHub 自动生成的 Source code 附件。本分支保持 `mod_id=mcef`，不能与原版一起安装。

兼容基线：**MCEF 2.2.0、Minecraft 26.1.1、NeoForge、Java 25**，用于 DivZero 原有 26.1.2 集成环境；不是其它 Minecraft/加载器版本的兼容承诺。平台构建、架构及安装器验证不等于游戏内渲染验收。浏览在线网页和访问 AI API 仍需网络。

## 来源与构建

上游旧地址 Keksuccino/mcef 已迁移为 Keksuccino/Rinku。本仓库导入 legacy 源码快照，不跟随 Rinku 新版 API：

- MCEF source: `e2a48d91ab08b5f5898ba440dbb69e57b6355615`
- JCEF source/native build: `eaeb3d4370aa3526ee237ad1981ad59af3de4dd1`

```sh
git clone --recurse-submodules https://github.com/gaoshanliuni/MCEF-Offline.git
cd MCEF-Offline
python offline/test.py
python offline/test_package.py
python offline/test_architecture.py
./gradlew :neoforge:jarJar :neoforge:sourcesJar --no-daemon
python offline/package.py base
python offline/package.py platform --base build/offline-base/mcef-offline-neoforge-api.jar --platform windows_amd64
```

Windows 使用 gradlew.bat；需要 Java 25、Python 3.11+。开发者/CI 构建会下载 Gradle、Minecraft 依赖及固定 JCEF 运行库；**玩家启动不会下载运行库**。

自动发版先编译公共基底，再分别构建四个平台，检查 JCEF/CEF 二进制的 PE/ELF/Mach-O 架构，实际执行包内提取/缓存复用/损坏修复测试，校验 SHA-256，全部通过后公开独立 JAR 附件、完整对应源码和许可证。发行标签含源码提交和工作流执行号，已发布版本不覆盖。不要安装失败工作流的中间产物。

## 下游编译接入

编译使用某个固定 Release 的 `mcef-offline-neoforge-api.jar` 并锁定 SHA-256。运行/发行时选同一 Release 的平台 JAR。版本和哈希应保存在下游仓库锁文件中，**不要依赖 latest 或浮动 main**。`mcef-offline-release.json` 给出平台包、API 包、源码的哈希/大小及构建标识，可供 DivZero 自动发版增加离线附件。

## 缓存、修复与测试

缓存位于实例工作目录 `mods/mcef-libraries/offline/<jcef-commit>/<platform>/`。通过进程锁、临时目录、压缩包及逐文件 SHA-256 校验后才切换当前版本指针；修复时不覆盖可能被其它进程加载的 DLL。保留 macOS 符号链接及 Unix 可执行权限，拒绝路径穿越和未知条目。旧缓存不会自动删除；关闭全部游戏后可清理这个专用缓存目录。

Windows/macOS/Linux 执行本地安装器单元测试；平台打包任务用真实 JAR 验证包内资源提取、复用和修复，但不加载浏览器原生代码。完整游戏验收仍需在游戏依赖已准备好的测试实例中断网启动，并检查本地网页渲染。

许可：LGPL-2.1-or-later。详见 LICENSE、offline/THIRD_PARTY_NOTICES.md；发行附件提供完整对应源码。离线打包不解决旧 Chromium 自身的安全问题。
