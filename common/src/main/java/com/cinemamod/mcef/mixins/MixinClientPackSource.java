/* SPDX-License-Identifier: LGPL-2.1-or-later
 * Offline initialization, modified for MCEF Offline in 2026.
 */
package com.cinemamod.mcef.mixins;

import com.cinemamod.mcef.MCEF;
import com.cinemamod.mcef.MCEFPlatform;
import com.cinemamod.mcef.internal.MCEFDownloadListener;
import com.cinemamod.mcef.offline.OfflineRuntime;
import net.minecraft.client.resources.ClientPackSource;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Unique;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;
import java.nio.file.Path;

@Mixin(ClientPackSource.class)
public class MixinClientPackSource {
    @Unique private static final Logger LOGGER = LoggerFactory.getLogger("MCEF");

    @Inject(at = @At("HEAD"), method = "<clinit>")
    private static void on_clinit_MCEF(CallbackInfo callbackInfo) {
        MCEFDownloadListener.INSTANCE.setDone(false);
        MCEFDownloadListener.INSTANCE.setFailed(false);
        MCEFDownloadListener.INSTANCE.setTask("Preparing bundled Chromium runtime (offline)");
        Thread installer = new Thread(MixinClientPackSource::installOffline_MCEF, "MCEF-Offline-Installer");
        installer.setDaemon(true);
        installer.start();
    }

    @Unique
    private static void installOffline_MCEF() {
        try {
            String commit = MCEF.getJavaCefCommit();
            String platform = MCEFPlatform.getPlatform().getNormalizedName();
            Path root = Path.of(".").toRealPath().resolve("mods/mcef-libraries/offline");
            Path installed = OfflineRuntime.install(root, platform, commit,
                    task -> MCEFDownloadListener.INSTANCE.setTask(task));
            System.setProperty("mcef.libraries.path", installed.getParent().toString());
            System.setProperty("jcef.path", installed.toString());
            LOGGER.info("MCEF Offline: local runtime ready at {} (JCEF {}, {}). No download was requested.", installed, commit, platform);
            MCEFDownloadListener.INSTANCE.setProgress(1.0f);
            MCEFDownloadListener.INSTANCE.setDone(true);
        } catch (Exception e) {
            LOGGER.error("MCEF Offline could not install/repair the bundled runtime. No network fallback will be attempted.", e);
            MCEFDownloadListener.INSTANCE.setTask("Offline runtime unavailable: check matching platform JAR and logs");
            MCEFDownloadListener.INSTANCE.setFailed(true);
        }
    }
}
