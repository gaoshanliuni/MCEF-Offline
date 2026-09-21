# MCEF Offline — source, license and distribution notices

MCEF Offline modifies the Java-side initialization/distribution of MCEF. Browser rendering APIs and the native Chromium/JCEF build are retained from the recorded upstream versions. This is an independent distribution, not an upstream endorsement.

- MCEF source: Keksuccino/Rinku, legacy commit `e2a48d91ab08b5f5898ba440dbb69e57b6355615`, originally developed by montoyo, CinemaMod contributors and Keksuccino. License: GNU LGPL 2.1 or later; complete terms are in repository `LICENSE` and release `LICENSE-MCEF.txt`.
- Local installer, packaging automation and offline modifications: MCEF Offline contributors, 2026, LGPL-2.1-or-later.
- Java Chromium Embedded Framework source: CinemaMod/java-cef commit `eaeb3d4370aa3526ee237ad1981ad59af3de4dd1`. Its copyright, redistribution conditions and disclaimer are retained in `common/java-cef/LICENSE.txt` and in each runtime JAR at `mcef-offline/licenses/JCEF-LICENSE.txt`.
- Native binaries are the corresponding CinemaMod JCEF/CEF builds. Native archive URL and actual SHA-256 are recorded separately for each platform in `MCEF-OFFLINE-<platform>.json`. All files from the native bundle, including any license/notice files, are preserved when converting its container format. CEF/Chromium and their components retain their respective licenses; do not remove their notices when redistributing extracted runtime files. Consult the bundled browser's credits and the upstream source notices for third-party component details.

The release `mcef-offline-corresponding-sources.jar` is a ZIP-format corresponding-source archive containing this fork's source, build/packaging scripts and the pinned JCEF Java source. It is NOT an installable mod. The exact fork commit is recorded in `mcef-offline-release.json`; the public repository provides the same source and build instructions. No private DivZero repository or history is included.

Install only ONE MCEF distribution at a time. Platform offline JARs use the original `mcef` mod identifier for compatibility. The API JAR is only a build dependency, not a player installation file.

These packages fix distribution/installation, not upstream browser security defects. Bundling a fixed Chromium build does not make untrusted webpages safe. Keep the browser source/runtime updated together when a compatible, tested upstream update is adopted.
