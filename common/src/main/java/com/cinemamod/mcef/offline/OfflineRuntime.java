/* SPDX-License-Identifier: LGPL-2.1-or-later
 * MCEF Offline: local-only browser runtime installation and repair.
 * Copyright (C) 2026 MCEF Offline contributors.
 */
package com.cinemamod.mcef.offline;

import java.io.*;
import java.nio.channels.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.nio.file.attribute.PosixFilePermission;
import java.security.*;
import java.util.*;
import java.util.function.Consumer;
import java.util.zip.*;

/** No HTTP client, download mirror, remote checksum, or network fallback. */
public final class OfflineRuntime {
    private static final LinkOption[] NOFOLLOW = {LinkOption.NOFOLLOW_LINKS};
    private static final long MAX_ARCHIVE = 2L * 1024 * 1024 * 1024;
    private static final long MAX_EXPANDED = 4L * 1024 * 1024 * 1024;
    private static final Set<String> PLATFORMS = Set.of("windows_amd64", "windows_arm64",
            "linux_amd64", "linux_arm64", "macos_amd64", "macos_arm64");

    @FunctionalInterface
    public interface Resources { InputStream open(String name) throws IOException; }

    private record Entry(String name, String hash, long size, boolean executable, String link) {}
    private record Bundle(String commit, String archiveHash, long archiveSize, List<Entry> entries) {}
    private OfflineRuntime() {}

    public static Path install(Path root, String platform, String expectedCommit,
                               Consumer<String> status) throws IOException {
        return install(root, platform, expectedCommit, OfflineRuntime.class::getResourceAsStream, status);
    }

    /** Resource injection is used by the standalone tests, not by a remote provider. */
    public static Path install(Path root, String platform, String expectedCommit,
                               Resources resources, Consumer<String> status) throws IOException {
        if (!PLATFORMS.contains(platform)) throw new IOException("Unsupported MCEF offline platform: " + platform);
        String prefix = "/mcef-offline/" + platform + "/";
        Bundle bundle = readBundle(resources, prefix, platform, expectedCommit);
        root = root.toAbsolutePath().normalize();
        safeDirectories(root);
        Path home = root.resolve(bundle.commit).resolve(platform);
        safeDirectories(home);
        Path lockPath = home.resolve("install.lock");
        if (Files.isSymbolicLink(lockPath)) throw new IOException("Unsafe MCEF installation lock");
        try (FileChannel channel = FileChannel.open(lockPath, StandardOpenOption.CREATE, StandardOpenOption.WRITE);
             FileLock ignored = lock(channel)) {
            Path pointer = home.resolve("current.txt");
            if (Files.isRegularFile(pointer, NOFOLLOW) && Files.size(pointer) < 256) {
                String current = Files.readString(pointer, StandardCharsets.US_ASCII).trim();
                if (current.matches("[a-f0-9]{64}-[a-f0-9-]{36}")) {
                    Path previous = home.resolve(current).resolve(platform);
                    status.accept("Checking local Chromium runtime");
                    if (valid(previous, bundle)) return previous;
                }
            }
            status.accept("Installing bundled Chromium runtime (offline)");
            Path staging = home.resolve("install-" + UUID.randomUUID());
            safeDirectories(staging);
            try {
                Path archive = staging.resolve("bundle.zip");
                try (InputStream source = require(resources, prefix + "runtime.zip")) {
                    copyChecked(source, archive, bundle.archiveSize, bundle.archiveHash);
                }
                Path extracted = staging.resolve("runtime").resolve(platform);
                safeDirectories(extracted);
                unpack(archive, extracted, bundle);
                Files.writeString(extracted.resolve(".complete"), bundle.archiveHash, StandardCharsets.US_ASCII,
                        StandardOpenOption.CREATE_NEW);
                if (!valid(extracted, bundle)) throw new IOException("Bundled MCEF runtime verification failed");
                // Never overwrite a directory whose DLLs may be loaded by another game process.
                Path installed = home.resolve(bundle.archiveHash + "-" + UUID.randomUUID());
                Files.move(extracted.getParent(), installed, StandardCopyOption.ATOMIC_MOVE);
                Path nextPointer = staging.resolve("current.txt");
                Files.writeString(nextPointer, installed.getFileName().toString(), StandardCharsets.US_ASCII);
                try {
                    Files.move(nextPointer, pointer, StandardCopyOption.ATOMIC_MOVE, StandardCopyOption.REPLACE_EXISTING);
                } catch (AtomicMoveNotSupportedException e) {
                    // The installation itself is already complete; a torn pointer is repaired next launch.
                    Files.move(nextPointer, pointer, StandardCopyOption.REPLACE_EXISTING);
                }
                status.accept("Bundled Chromium runtime ready");
                return installed.resolve(platform);
            } finally {
                // Only our newly-created staging directory; never delete user data or older installations.
                deleteStaging(staging);
            }
        }
    }

    private static FileLock lock(FileChannel channel) throws IOException {
        long deadline = System.nanoTime() + 120_000_000_000L;
        while (System.nanoTime() < deadline) {
            try {
                FileLock lock = channel.tryLock();
                if (lock != null) return lock;
            } catch (OverlappingFileLockException ignored) { }
            try { Thread.sleep(100); }
            catch (InterruptedException e) { Thread.currentThread().interrupt(); throw new IOException("MCEF install cancelled", e); }
        }
        throw new IOException("Another process is installing MCEF; timed out waiting for the installation lock");
    }

    private static Bundle readBundle(Resources source, String prefix, String platform, String expectedCommit) throws IOException {
        Properties p = new Properties();
        try (InputStream in = require(source, prefix + "runtime.properties")) {
            byte[] bytes = in.readNBytes(4 * 1024 * 1024 + 1);
            if (bytes.length > 4 * 1024 * 1024) throw new IOException("MCEF manifest is too large");
            p.load(new ByteArrayInputStream(bytes));
        }
        try {
            if (!"1".equals(p.getProperty("format")) || !platform.equals(p.getProperty("platform")))
                throw new IOException("MCEF offline manifest/platform mismatch");
            String commit = p.getProperty("commit", "");
            if (!commit.matches("[a-f0-9]{40}") || !commit.equals(expectedCommit))
                throw new IOException("MCEF offline JCEF commit mismatch");
            String archiveHash = p.getProperty("archive.sha256", "");
            long archiveSize = Long.parseLong(p.getProperty("archive.size"));
            if (!archiveHash.matches("[a-f0-9]{64}") || archiveSize <= 0 || archiveSize > MAX_ARCHIVE)
                throw new IOException("Invalid MCEF bundled archive identity");
            int count = Integer.parseInt(p.getProperty("entry.count"));
            if (count <= 0 || count > 50_000) throw new IOException("Invalid MCEF entry count");
            List<Entry> entries = new ArrayList<>();
            Set<String> names = new HashSet<>();
            long total = 0;
            for (int i = 0; i < count; i++) {
                String key = "entry." + i + ".";
                String name = decode(p.getProperty(key + "path"));
                relative(name);
                if (name.equals(".complete") || !names.add(name)) throw new IOException("Duplicate/reserved MCEF path");
                String type = p.getProperty(key + "type");
                if ("file".equals(type)) {
                    String hash = p.getProperty(key + "sha256", "");
                    long size = Long.parseLong(p.getProperty(key + "size"));
                    if (!hash.matches("[a-f0-9]{64}") || size < 0 || size > MAX_EXPANDED)
                        throw new IOException("Invalid MCEF file identity");
                    total += size;
                    if (total > MAX_EXPANDED) throw new IOException("MCEF expansion exceeds the size limit");
                    entries.add(new Entry(name, hash, size, "true".equals(p.getProperty(key + "executable")), null));
                } else if ("link".equals(type)) {
                    String target = decode(p.getProperty(key + "target"));
                    linkTarget(name, target);
                    entries.add(new Entry(name, "", 0, false, target));
                } else throw new IOException("Unsupported MCEF entry type");
            }
            for (Entry entry : entries) {
                Path parent = relative(entry.name).getParent();
                while (parent != null) {
                    if (names.contains(parent.toString().replace(File.separatorChar, '/')))
                        throw new IOException("MCEF manifest contains a file/link used as a parent directory");
                    parent = parent.getParent();
                }
            }
            return new Bundle(commit, archiveHash, archiveSize, List.copyOf(entries));
        } catch (IllegalArgumentException | NullPointerException e) {
            throw new IOException("Malformed MCEF offline manifest", e);
        }
    }

    private static void unpack(Path archive, Path destination, Bundle bundle) throws IOException {
        Map<String, Entry> files = new HashMap<>();
        for (Entry entry : bundle.entries) if (entry.link == null) files.put(entry.name, entry);
        try (ZipInputStream zip = new ZipInputStream(Files.newInputStream(archive))) {
            ZipEntry zipped;
            while ((zipped = zip.getNextEntry()) != null) {
                Entry entry = files.remove(zipped.getName());
                if (zipped.isDirectory() || entry == null) throw new IOException("Unexpected/duplicate MCEF archive entry: " + zipped.getName());
                Path file = destination.resolve(relative(entry.name));
                safeDirectories(file.getParent());
                copyChecked(zip, file, entry.size, entry.hash);
                if (entry.executable && Files.getFileStore(file).supportsFileAttributeView("posix")) {
                    Set<PosixFilePermission> mode = new HashSet<>(Files.getPosixFilePermissions(file, NOFOLLOW));
                    mode.add(PosixFilePermission.OWNER_EXECUTE);
                    mode.add(PosixFilePermission.GROUP_EXECUTE);
                    mode.add(PosixFilePermission.OTHERS_EXECUTE);
                    Files.setPosixFilePermissions(file, mode);
                }
                zip.closeEntry();
            }
        }
        if (!files.isEmpty()) throw new IOException("MCEF archive is missing expected files");
        for (Entry entry : bundle.entries) if (entry.link != null) {
            Path file = destination.resolve(relative(entry.name));
            safeDirectories(file.getParent());
            Files.createSymbolicLink(file, Path.of(entry.link));
        }
    }

    private static boolean valid(Path root, Bundle bundle) throws IOException {
        if (!Files.isDirectory(root, NOFOLLOW)) return false;
        Path marker = root.resolve(".complete");
        if (!Files.isRegularFile(marker, NOFOLLOW) || Files.size(marker) != 64
                || !bundle.archiveHash.equals(Files.readString(marker, StandardCharsets.US_ASCII))) return false;
        for (Entry entry : bundle.entries) {
            Path file = root.resolve(relative(entry.name));
            for (Path parent = file.getParent(); parent != null && parent.startsWith(root); parent = parent.getParent())
                if (!Files.isDirectory(parent, NOFOLLOW)) return false;
            if (entry.link != null) {
                if (!Files.isSymbolicLink(file) || !Files.readSymbolicLink(file).toString().equals(entry.link)) return false;
            } else {
                if (!Files.isRegularFile(file, NOFOLLOW) || Files.size(file) != entry.size) return false;
                try (InputStream in = Files.newInputStream(file)) {
                    if (!digest(in).equals(entry.hash)) return false;
                }
                if (entry.executable && Files.getFileStore(file).supportsFileAttributeView("posix") && !Files.isExecutable(file)) return false;
            }
        }
        return true;
    }

    private static Path relative(String name) throws IOException {
        if (name.isEmpty() || name.startsWith("/") || name.contains("\\") || name.contains(":") || name.indexOf('\0') >= 0)
            throw new IOException("Unsafe MCEF path");
        for (String part : name.split("/", -1))
            if (part.isEmpty() || part.equals(".") || part.equals("..")) throw new IOException("Unsafe MCEF path segment");
        Path path = Path.of(name);
        if (path.isAbsolute()) throw new IOException("Absolute MCEF path");
        return path;
    }

    private static void linkTarget(String name, String target) throws IOException {
        if (target.isEmpty() || target.contains("\\") || target.contains(":") || Path.of(target).isAbsolute())
            throw new IOException("Unsafe MCEF link");
        Path root = Path.of("bundle").toAbsolutePath();
        Path resolved = root.resolve(relative(name)).getParent().resolve(target).normalize();
        if (!resolved.startsWith(root)) throw new IOException("MCEF link escapes the installation");
    }

    private static String decode(String value) { return new String(Base64.getUrlDecoder().decode(value), StandardCharsets.UTF_8); }
    private static InputStream require(Resources source, String name) throws IOException {
        InputStream input = source.open(name);
        if (input == null) throw new IOException("This MCEF JAR has no bundled runtime for this platform. Install the matching platform offline JAR (not the API/sources JAR): " + name);
        return input;
    }
    private static MessageDigest sha256() {
        try { return MessageDigest.getInstance("SHA-256"); }
        catch (NoSuchAlgorithmException e) { throw new AssertionError(e); }
    }
    private static String digest(InputStream in) throws IOException {
        MessageDigest digest = sha256();
        byte[] bytes = new byte[64 * 1024];
        int n;
        while ((n = in.read(bytes)) != -1) digest.update(bytes, 0, n);
        return HexFormat.of().formatHex(digest.digest());
    }
    private static void copyChecked(InputStream in, Path file, long expectedSize, String expectedHash) throws IOException {
        MessageDigest digest = sha256();
        long count = 0;
        try (OutputStream out = Files.newOutputStream(file, StandardOpenOption.CREATE_NEW)) {
            byte[] bytes = new byte[64 * 1024];
            int n;
            while ((n = in.read(bytes)) != -1) {
                count += n;
                if (count > expectedSize) throw new IOException("Oversized MCEF archive/file");
                digest.update(bytes, 0, n);
                out.write(bytes, 0, n);
            }
        }
        if (count != expectedSize || !expectedHash.equals(HexFormat.of().formatHex(digest.digest())))
            throw new IOException("MCEF bundled file SHA-256/size mismatch");
    }
    private static void safeDirectories(Path path) throws IOException {
        Path absolute = path.toAbsolutePath().normalize();
        for (Path current = absolute.getRoot(); current != null;) {
            if (Files.exists(current, NOFOLLOW) && !Files.isDirectory(current, NOFOLLOW))
                throw new IOException("MCEF installation path contains a symbolic link or non-directory: " + current);
            if (current.equals(absolute)) break;
            current = current.resolve(absolute.getName(current.getNameCount()));
        }
        Files.createDirectories(absolute);
    }
    private static void deleteStaging(Path root) {
        try {
            if (Files.isDirectory(root, NOFOLLOW)) {
                try (var files = Files.walk(root)) {
                    for (Path p : files.sorted(Comparator.reverseOrder()).toList()) Files.deleteIfExists(p);
                }
            }
        } catch (IOException ignored) { /* A leftover unique staging directory is never considered installed. */ }
    }
}
