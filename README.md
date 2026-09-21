# MCEF Offline

Platform-specific offline distribution of MCEF for DivZero. Based on Keksuccino's MCEF 2.2.0 for Minecraft 26.1.1 / NeoForge (upstream repository renamed to `Keksuccino/Rinku`).

Upstream source baseline: `e2a48d91ab08b5f5898ba440dbb69e57b6355615`.
JCEF source/native build baseline: `eaeb3d4370aa3526ee237ad1981ad59af3de4dd1`.

The offline fork bundles one platform's browser runtime in each installable JAR and installs/repairs it locally. Browser runtime initialization must never require an Internet connection. Online webpages still require network access.

Source and distribution automation are being initialized in this repository. Only assets from a completed, verified release are installable builds; a source checkout or a source ZIP is not an installable mod.

MCEF modifications are distributed under LGPL-2.1-or-later. Upstream and bundled third-party license notices must accompany release artifacts.
