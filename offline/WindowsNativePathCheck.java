import com.cinemamod.mcef.offline.OfflineRuntime;
import org.cef.CefApp;
import java.io.IOException;
import java.nio.file.*;
import java.util.Locale;

/** Exercise System.load via real JCEF startup, not only extraction on a Linux runner. */
public final class WindowsNativePathCheck {
    private static final String COMMIT = "eaeb3d4370aa3526ee237ad1981ad59af3de4dd1";
    public static void main(String[] args) throws Exception {
        if (!System.getProperty("os.name").toLowerCase(Locale.ROOT).startsWith("windows"))
            throw new IllegalStateException("This regression test requires Windows");
        if (System.getProperty("mcef.offline.cacheDir") != null)
            throw new IllegalStateException("Test must start with the default cache policy");
        Path game = Files.createTempDirectory("mcef-game-path-test-").toRealPath()
                .resolve("launcher/instances/long-instance-name-for-native-path-regression")
                .resolve("versions/26.1.2-NeoForge_26.1.2.106/中文游戏目录");
        Files.createDirectories(game);
        Path legacy = game.resolve("mods/mcef-libraries/offline").resolve(COMMIT).resolve("windows_amd64")
                .resolve("a".repeat(64) + "-00000000-0000-0000-0000-000000000000")
                .resolve("windows_amd64/chrome_elf.dll");
        if (legacy.toString().length() <= 260) throw new AssertionError("Fixture does not reproduce the old overlong path");
        Path installed = OfflineRuntime.installForGame(game, "windows_amd64", COMMIT, System.out::println);
        if (installed.startsWith(game)) throw new AssertionError("Windows natives still depend on the game's long path");
        if (installed.resolve("chrome_elf.dll").toString().length() > 240)
            throw new AssertionError("Native library path is over budget");
        if (!installed.equals(OfflineRuntime.installForGame(game, "windows_amd64", COMMIT, System.out::println)))
            throw new AssertionError("Default local cache not reused");
        Path oversizedOverride = game.resolve("intentionally-overlong-cache-".repeat(3));
        System.setProperty("mcef.offline.cacheDir", oversizedOverride.toString());
        try {
            OfflineRuntime.installForGame(game, "windows_amd64", COMMIT, ignored -> {});
            throw new AssertionError("Oversized explicit cache should fail before loading natives");
        } catch (IOException expected) {
            if (Files.exists(oversizedOverride)) throw new AssertionError("Rejected explicit root was written");
        } finally { System.clearProperty("mcef.offline.cacheDir"); }
        System.setProperty("mcef.libraries.path", installed.getParent().toString());
        System.setProperty("jcef.path", installed.toString());
        // Same Windows System.load chain as the in-game stack trace, including chrome_elf.dll.
        if (!CefApp.startup(new String[0])) throw new AssertionError("JCEF startup failed");
        System.out.println("WINDOWS_NATIVE_PATH_REGRESSION_PASSED old=" + legacy.toString().length()
                + " new=" + installed.resolve("chrome_elf.dll").toString().length()
                + " vendor=" + System.getProperty("java.vendor"));
        // This is a DLL-load smoke test, not a rendered browser/in-game acceptance test.
    }
}
