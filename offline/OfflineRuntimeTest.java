package com.cinemamod.mcef.offline;

import java.io.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.security.MessageDigest;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.zip.*;

public final class OfflineRuntimeTest {
    static final String COMMIT = "0123456789012345678901234567890123456789";
    static final String PLATFORM = "linux_amd64";
    static final String PREFIX = "/mcef-offline/" + PLATFORM + "/";
    static int assertions;
    static void check(boolean value, String message) { assertions++; if (!value) throw new AssertionError(message); }
    static String hash(byte[] bytes) throws Exception { return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(bytes)); }
    static String b64(String s) { return Base64.getUrlEncoder().withoutPadding().encodeToString(s.getBytes(StandardCharsets.UTF_8)); }
    static Map<String, byte[]> fixture(String path) throws Exception {
        byte[] data = "fake-native-runtime-for-installer-tests".getBytes(StandardCharsets.UTF_8);
        ByteArrayOutputStream bytes = new ByteArrayOutputStream();
        try (ZipOutputStream zip = new ZipOutputStream(bytes)) { zip.putNextEntry(new ZipEntry(path)); zip.write(data); zip.closeEntry(); }
        byte[] archive = bytes.toByteArray();
        String manifest = "format=1\nplatform="+PLATFORM+"\ncommit="+COMMIT+"\narchive.sha256="+hash(archive)+"\narchive.size="+archive.length
                +"\nentry.count=1\nentry.0.path="+b64(path)+"\nentry.0.type=file\nentry.0.sha256="+hash(data)
                +"\nentry.0.size="+data.length+"\nentry.0.executable=true\n";
        Map<String, byte[]> resources = new HashMap<>();
        resources.put(PREFIX+"runtime.zip", archive);
        resources.put(PREFIX+"runtime.properties", manifest.getBytes(StandardCharsets.US_ASCII));
        return resources;
    }
    static Path install(Path root, Map<String, byte[]> fixture, AtomicInteger reads) throws IOException {
        return OfflineRuntime.install(root, PLATFORM, COMMIT, name -> {
            byte[] bytes = fixture.get(name);
            if (name.endsWith(".zip")) reads.incrementAndGet();
            return bytes == null ? null : new ByteArrayInputStream(bytes);
        }, ignored -> {});
    }
    interface Attempt { void run() throws Exception; }
    static void fails(Attempt action, String message) throws Exception {
        try { action.run(); throw new AssertionError(message); } catch (IOException expected) { assertions++; }
    }
    public static void main(String[] args) throws Exception {
        Path base = Files.createTempDirectory("mcef-offline-test-").toRealPath();
        var fixture = fixture("bin/native.bin");
        AtomicInteger reads = new AtomicInteger();
        Path first = install(base.resolve("normal"), fixture, reads);
        check(Files.isRegularFile(first.resolve("bin/native.bin")), "fresh install");
        check(reads.get() == 1, "one local archive read");
        check(first.equals(install(base.resolve("normal"), fixture, reads)), "reuse verified local installation");
        check(reads.get() == 1, "cached install does not reopen embedded archive");
        Files.writeString(first.resolve("bin/native.bin"), "corrupt");
        Path repaired = install(base.resolve("normal"), fixture, reads);
        check(!first.equals(repaired), "repair creates new generation");
        check(Files.readString(repaired.resolve("bin/native.bin")).startsWith("fake-native"), "repair restores bytes");
        check(Files.exists(first), "old possibly loaded native directory retained");
        Files.delete(repaired.resolve(".complete"));
        check(!repaired.equals(install(base.resolve("normal"), fixture, reads)), "missing complete marker repairs");
        fails(() -> install(base.resolve("missing"), Map.of(), reads), "missing bundle must fail offline");
        fails(() -> install(base.resolve("traversal"), fixture("../escape.bin"), reads), "reject path traversal");
        check(!Files.exists(base.resolve("escape.bin")), "no traversal writes");
        Map<String,byte[]> truncated = new HashMap<>(fixture);
        truncated.put(PREFIX+"runtime.zip", new byte[]{1,2,3});
        fails(() -> install(base.resolve("truncated"), truncated, reads), "truncated bundle must fail");
        check(!Files.exists(base.resolve("truncated").resolve(COMMIT).resolve(PLATFORM).resolve("current.txt")), "failed install not marked complete");
        fails(() -> OfflineRuntime.install(base.resolve("wrong"), PLATFORM, "f".repeat(40),
                name -> new ByteArrayInputStream(fixture.get(name)), ignored -> {}), "wrong commit must fail");
        ExecutorService pool = Executors.newFixedThreadPool(2);
        try {
            var a = pool.submit(() -> install(base.resolve("concurrent"), fixture, reads));
            var b = pool.submit(() -> install(base.resolve("concurrent"), fixture, reads));
            check(a.get().equals(b.get()), "concurrent installers share one verified generation");
        } finally { pool.shutdownNow(); }
        if (!System.getProperty("os.name").toLowerCase(Locale.ROOT).startsWith("windows")) {
            Path target = Files.createDirectory(base.resolve("outside"));
            Path root = Files.createDirectory(base.resolve("symlink"));
            Files.createSymbolicLink(root.resolve(COMMIT), target);
            fails(() -> install(root, fixture, reads), "reject symlink installation directory");
            try (var files = Files.list(target)) { check(files.findAny().isEmpty(), "no writes through symbolic link"); }
            check(Files.isExecutable(install(base.resolve("permissions"), fixture, reads).resolve("bin/native.bin")), "preserve executable permission");
        }
        System.out.println("MCEF_OFFLINE_INSTALLER_TESTS_PASSED=" + assertions);
    }
}
