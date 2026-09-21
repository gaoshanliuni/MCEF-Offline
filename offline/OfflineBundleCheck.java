import com.cinemamod.mcef.offline.OfflineRuntime;
import java.nio.file.*;

/** Exercises the actual packaged JAR resource path without executing browser natives. */
public class OfflineBundleCheck {
    public static void main(String[] args) throws Exception {
        if (args.length != 2) throw new IllegalArgumentException("platform and pinned JCEF commit required");
        Path cache = Files.createTempDirectory("mcef-real-bundle-").toRealPath();
        Path first = OfflineRuntime.install(cache, args[0], args[1], System.out::println);
        Path reused = OfflineRuntime.install(cache, args[0], args[1], System.out::println);
        if (!first.equals(reused)) throw new AssertionError("Unmodified runtime not reused");
        Path sample;
        try (var files = Files.walk(first)) {
            sample = files.filter(p -> Files.isRegularFile(p, LinkOption.NOFOLLOW_LINKS)
                    && !p.getFileName().toString().equals(".complete")).findFirst().orElseThrow();
        }
        Files.writeString(sample, "intentional corruption in disposable CI test cache");
        Path repaired = OfflineRuntime.install(cache, args[0], args[1], System.out::println);
        if (first.equals(repaired) || !Files.exists(first)) throw new AssertionError("Repair must create a new generation");
        if (!repaired.equals(OfflineRuntime.install(cache, args[0], args[1], System.out::println)))
            throw new AssertionError("Repaired runtime failed validation");
        System.out.println("REAL_BUNDLED_RUNTIME_INSTALL_REUSE_REPAIR_PASSED=" + args[0]);
    }
}
