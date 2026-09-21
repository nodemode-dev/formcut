#!/usr/bin/env python3
"""merge_macos_bundle v1.0.0

Adds a bundle made by build_ffmpeg_lgpl_macos to formcut's src-tauri/binaries/
folder, and rewrites that target's entry in ffmpeg-licence.json and its row in
README-ffmpeg.md from what it finds in the files, never from what it is told.

    python3 merge_macos_bundle_v1.0.0.py BUNDLE BINARIES_DIR

BUNDLE is the bundle directory or its ffmpeg-lgpl-<triple>.tar.gz. Nothing in
BINARIES_DIR changes unless every check passes. Standard library only.
"""
import datetime, hashlib, json, os, platform, re, shutil, struct
import subprocess, sys, tarfile, tempfile

VERSION = "v1.0.0"
TRIPLES = {"aarch64-apple-darwin": "arm64", "x86_64-apple-darwin": "x86_64"}
CPU = {0x0100000C: "arm64", 0x01000007: "x86_64"}
FORBIDDEN = re.compile(r"enable-gpl|enable-nonfree|libx264|libx265|libfdk")


class Refuse(Exception):
    pass


def say(msg):
    print("== " + msg)


def step(msg):
    print("   " + msg)


# ---------------------------------------------------------------- Mach-O ----

def macho(path):
    raw = open(path, "rb").read()
    if len(raw) < 32 or struct.unpack("<I", raw[:4])[0] != 0xFEEDFACF:
        raise Refuse("%s is not a thin 64-bit Mach-O file" % os.path.basename(path))
    _, cpu, _, ftype, ncmds, _, _, _ = struct.unpack_from("<IiiIIIII", raw, 0)
    info = {"arch": CPU.get(cpu & 0xFFFFFFFF, hex(cpu)), "id": None, "deps": [],
            "rpaths": [], "minos": None, "sdk": None, "signed": False}
    off = 32

    def cstr(o):
        return raw[o:raw.index(b"\0", o)].decode()

    def ver(v):
        return "%d.%d.%d" % (v >> 16, (v >> 8) & 0xFF, v & 0xFF)

    for _ in range(ncmds):
        cmd, size = struct.unpack_from("<II", raw, off)
        if cmd in (0x0C, 0x0D, 0x80000018, 0x8000001F):
            name = cstr(off + struct.unpack_from("<I", raw, off + 8)[0])
            if cmd == 0x0D:
                info["id"] = name
            else:
                info["deps"].append(name)
        elif cmd == 0x8000001C:
            info["rpaths"].append(cstr(off + struct.unpack_from("<I", raw, off + 8)[0]))
        elif cmd == 0x32:
            _, minos, sdk = struct.unpack_from("<III", raw, off + 8)
            info["minos"], info["sdk"] = ver(minos), ver(sdk)
        elif cmd == 0x24:
            v, sdk = struct.unpack_from("<II", raw, off + 8)
            info["minos"], info["sdk"] = ver(v), ver(sdk)
        elif cmd == 0x1D:
            info["signed"] = True
        off += size
    return info


def vtuple(v):
    # Padded to three parts: Python ranks (11, 0, 0) above (11, 0) otherwise,
    # which refused a correct minos 11.0.0 against a deployment target of 11.0.
    parts = [int(x) for x in v.split(".")]
    return tuple(parts + [0] * (3 - len(parts)))


def vshort(v):
    parts = v.split(".")
    return ".".join(parts[:2]) if parts[2:] == ["0"] else v


def sha(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


# ---------------------------------------------------------------- checks ----

def stage(src, tmp):
    if os.path.isdir(src):
        root = src
    elif src.endswith(".tar.gz"):
        with tarfile.open(src) as t:
            for m in t.getmembers():
                if m.issym() or m.islnk():
                    raise Refuse("the tarball contains a link: %s" % m.name)
            t.extractall(tmp)
        root = tmp
    else:
        raise Refuse("give a bundle directory or its .tar.gz")
    for a, _, fs in os.walk(root):
        if "MANIFEST.json" in fs:
            return a
    raise Refuse("no MANIFEST.json found in %s" % src)


def check_bundle(b, record):
    say("checking the bundle")
    man = json.load(open(os.path.join(b, "MANIFEST.json")))
    triple = man.get("triple")
    if triple not in TRIPLES:
        raise Refuse("the bundle is for %r; this tool merges macOS bundles only" % triple)
    arch = TRIPLES[triple]
    step("target %s" % triple)

    want = record["source"]["ffmpeg"]
    got_v, got_s = man["ffmpeg"]["version"], man["ffmpeg"]["source_sha256"]
    if (got_v, got_s) != (want["version"], want["sha256"]):
        raise Refuse("the bundle is FFmpeg %s from source %s..., but every target in the record\n"
                     "   is %s from %s.... Merging it would bring back the version skew."
                     % (got_v, got_s[:12], want["version"], want["sha256"][:12]))
    step("FFmpeg %s, same source tarball as every other target" % got_v)

    for a, _, fs in os.walk(b):
        for f in fs:
            if os.path.islink(os.path.join(a, f)):
                raise Refuse("symbolic link in the bundle: %s" % f)

    listed = {f["path"]: f for f in man["files"]}
    for p, f in listed.items():
        full = os.path.join(b, p)
        if not os.path.isfile(full) or os.path.getsize(full) != f["bytes"] or sha(full) != f["sha256"]:
            raise Refuse("%s does not match its MANIFEST.json entry" % p)
    step("%d files match MANIFEST.json" % len(listed))

    progs = ["ffmpeg-" + triple, "ffprobe-" + triple]
    libdir = "lib-" + triple
    libs = sorted(os.listdir(os.path.join(b, libdir)))
    if len(libs) != 7:
        raise Refuse("expected 7 libraries in %s, found %d" % (libdir, len(libs)))

    target_min = man.get("deployment_target", "11.0")
    minos, sdks = set(), set()
    for p in progs + [os.path.join(libdir, x) for x in libs]:
        m = macho(os.path.join(b, p))
        name = os.path.basename(p)
        if m["arch"] != arch:
            raise Refuse("%s is %s, not %s" % (name, m["arch"], arch))
        if not m["signed"]:
            raise Refuse("%s has no code signature" % name)
        if m["minos"] is None or vtuple(m["minos"]) > vtuple(target_min):
            raise Refuse("%s requires macOS %s, above the stated %s" % (name, m["minos"], target_min))
        minos.add(m["minos"])
        sdks.add(m["sdk"])
        for d in m["deps"]:
            if d.startswith(("/usr/lib/", "/System/Library/")):
                continue
            if not d.startswith("@rpath/"):
                raise Refuse("%s depends on %s, outside the bundle" % (name, d))
            if d[len("@rpath/"):] not in libs:
                raise Refuse("%s needs %s and %s does not have it" % (name, d, libdir))
        if p in progs:
            if "@executable_path/" + libdir not in m["rpaths"]:
                raise Refuse("%s lacks the rpath @executable_path/%s" % (name, libdir))
        else:
            if m["id"] != "@rpath/" + name:
                raise Refuse("%s has install name %s, not @rpath/%s" % (name, m["id"], name))
            if "@loader_path" not in m["rpaths"]:
                raise Refuse("%s lacks the rpath @loader_path" % name)
    step("all 9 Mach-O files are %s, signed, minos %s, every dependency resolved" % (arch, "/".join(sorted(minos))))

    conf_lines = [l.strip() for l in open(os.path.join(b, "BUILDCONF.txt")) if l.strip().startswith("--")]
    configure = " ".join(conf_lines)
    if FORBIDDEN.search(configure) or "--disable-gpl" not in configure:
        raise Refuse("BUILDCONF.txt names a GPL or nonfree component, or lacks --disable-gpl")
    conf_arch = re.search(r"--arch=(\S+)", configure)
    if conf_arch and conf_arch.group(1) != arch:
        raise Refuse("BUILDCONF.txt says --arch=%s but the binaries are %s" % (conf_arch.group(1), arch))
    step("configure line clean: no gpl, nonfree, x264, x265 or fdk; --arch matches")

    return {"man": man, "triple": triple, "arch": arch, "progs": progs, "libdir": libdir,
            "libs": libs, "configure": configure, "minos": max(minos, key=vtuple),
            "sdk": "/".join(sorted(s for s in sdks if s))}


def can_execute(arch):
    if platform.system() != "Darwin":
        return False, "this machine is not a Mac"
    host = platform.machine()
    if host == arch:
        return True, ""
    if host == "arm64" and arch == "x86_64":
        ok = subprocess.run(["arch", "-x86_64", "/usr/bin/true"], capture_output=True).returncode == 0
        return (True, "") if ok else (False, "this Apple silicon Mac has no Rosetta 2")
    return False, "an Intel Mac cannot run arm64 code"


def execute(b, info):
    """Run the bundle from a fresh directory with an empty environment."""
    say("executing it somewhere it was not built")
    ok, why = can_execute(info["arch"])
    if not ok:
        step("not executed: " + why)
        return {"method": "static only", "checks": [
            "Mach-O load commands read directly: %s, minos %s, code signature present, "
            "no dependency outside @rpath, /usr/lib and /System/Library" % (info["arch"], info["minos"]),
            "not executed by this merge: " + why]}
    room = tempfile.mkdtemp(prefix="ffmerge-")
    try:
        for p in info["progs"]:
            shutil.copy2(os.path.join(b, p), room)
        shutil.copytree(os.path.join(b, info["libdir"]), os.path.join(room, info["libdir"]))
        ff, fp = (os.path.join(room, p) for p in info["progs"])

        def run(args, **kw):
            r = subprocess.run(args, env={}, cwd=room, capture_output=True, **kw)
            if r.returncode != 0:
                raise Refuse("%s failed:\n%s" % (" ".join(os.path.basename(a) for a in args[:3]),
                                                  (r.stderr or b"").decode(errors="replace")[-800:]))
            return r.stdout

        v1 = run([ff, "-hide_banner", "-version"]).decode().splitlines()[0]
        run([fp, "-hide_banner", "-version"])
        step(v1)
        run([ff, "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi",
             "-i", "testsrc=size=320x180:rate=30:duration=2", "-c:v", "mpeg4", "a.mp4"])
        rb = run([fp, "-v", "error", "-select_streams", "v:0", "-show_entries",
                  "stream=codec_name,width,height", "-of", "csv=p=0", "a.mp4"]).decode().strip()
        if rb != "mpeg4,320,180":
            raise Refuse("read back %r, expected mpeg4,320,180" % rb)
        step("mpeg4 encoded and read back: " + rb)
        run([ff, "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi",
             "-i", "color=c=red@0.5:s=320x180:d=1,format=yuva420p", "-f", "lavfi", "-i", "sine=d=1",
             "-c:v", "libvpx-vp9", "-pix_fmt", "yuva420p", "-auto-alt-ref", "0",
             "-c:a", "libopus", "-shortest", "b.webm"])
        alpha = run([ff, "-loglevel", "error", "-c:v", "libvpx-vp9", "-i", "b.webm", "-frames:v", "1",
                     "-vf", "alphaextract", "-pix_fmt", "gray", "-f", "rawvideo", "-"])
        lo, hi = min(alpha), max(alpha)
        if not (100 <= lo <= hi <= 155):
            raise Refuse("alpha read back as %d..%d from a 50%% source" % (lo, hi))
        step("VP9 with alpha plus Opus: alpha read back %d..%d from a 50%% source" % (lo, hi))
        return {"method": "executed", "checks": [
            "copied to a fresh directory and run with an empty environment on %s %s"
            % (platform.system(), platform.machine()) + (" under Rosetta 2" if platform.machine() != info["arch"] else ""),
            v1, "mpeg4 clip encoded and read back as " + rb,
            "VP9 with alpha plus Opus encoded; 50%%-opacity source decoded through libvpx-vp9 reads back alpha %d..%d" % (lo, hi)]}
    finally:
        shutil.rmtree(room, ignore_errors=True)


# ------------------------------------------------------------------ merge ----

README_ROW = ("| `{t}` | `ffmpeg-…`, `ffprobe-…` | `lib-{t}/`, 7 dylibs "
              "| `@rpath`, via `@executable_path/lib-…` | {v} |")


def merge(b, info, verification, bin_dir, record):
    t, man = info["triple"], info["man"]
    say("adding %s to %s" % (t, bin_dir))
    for p in info["progs"]:
        dst = os.path.join(bin_dir, p)
        if os.path.exists(dst):
            os.remove(dst)
        shutil.copy2(os.path.join(b, p), dst)
    dst_lib = os.path.join(bin_dir, info["libdir"])
    if os.path.exists(dst_lib):
        shutil.rmtree(dst_lib)
    shutil.copytree(os.path.join(b, info["libdir"]), dst_lib)
    step("copied 2 programs and %s/" % info["libdir"])

    host = man.get("build_host", "unknown")
    files = []
    for p in info["progs"] + [os.path.join(info["libdir"], x) for x in info["libs"]]:
        full = os.path.join(bin_dir, p)
        files.append({"path": p, "sha256": sha(full), "bytes": os.path.getsize(full)})
    record["targets"][t] = {
        "status": "shipped", "ffmpeg": man["ffmpeg"]["version"],
        "programs": info["progs"], "library_dir": info["libdir"],
        "libraries_found_by": "install names @rpath/<name>; the programs carry LC_RPATH "
                              "@executable_path/%s and each library carries @loader_path" % info["libdir"],
        "must_stay_together": "the two programs and %s/ must remain siblings wherever they are installed" % info["libdir"],
        "minimum_os": "macOS %s (LC_BUILD_VERSION minos on every Mach-O)" % vshort(info["minos"]),
        "toolchain": "Apple clang, macOS %s SDK, on macOS %s" % (info["sdk"], host),
        "cross_built": not host.endswith(info["arch"]),
        "built_by": man.get("produced_by", "unknown"),
        "configure": info["configure"],
        "static_libraries": ["%s %s" % (l["name"], l["version"]) for l in man.get("bundled_libraries", [])],
        "licence_gates": {
            "binary_configure": "no --enable-gpl, --enable-nonfree, libx264, libx265 or libfdk (read here from BUILDCONF.txt)",
            "configure_reported_and_config_h": "enforced by %s at build time, which refuses otherwise; not re-observed here"
                                               % man.get("produced_by", "the build script")},
        "verification": verification,
        "files": files}
    record["written_utc"] = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with open(os.path.join(bin_dir, "ffmpeg-licence.json"), "w") as fh:
        json.dump(record, fh, indent=2)
        fh.write("\n")
    step("ffmpeg-licence.json: %s entry rewritten from the files" % t)

    rp = os.path.join(bin_dir, "README-ffmpeg.md")
    readme = open(rp, encoding="utf-8").read()
    v = "executed in a clean room" if verification["method"] == "executed" else "load commands read; not executed"
    row = README_ROW.format(t=t, v=v)
    lines = readme.split("\n")
    hits = [i for i, l in enumerate(lines) if l.startswith("| `%s` |" % t)]
    if len(hits) == 1:
        lines[hits[0]] = row
        readme = "\n".join(lines)
        step("README row for %s updated" % t)
    else:
        step("README: could not find exactly one row for %s; add this row by hand:" % t)
        step("  " + row)
    if t == "x86_64-apple-darwin":
        new = re.sub(r"## The missing target\n.*?(?=\n## )", "", readme, flags=re.S)
        if new != readme:
            readme = new
            step("README: 'The missing target' section removed")
    open(rp, "w", encoding="utf-8").write(readme)


def recheck(bin_dir):
    say("re-checking the whole folder against the record")
    record = json.load(open(os.path.join(bin_dir, "ffmpeg-licence.json")))
    n = 0
    for t, v in record["targets"].items():
        for f in v.get("files", []):
            full = os.path.join(bin_dir, f["path"])
            if not os.path.isfile(full) or sha(full) != f["sha256"]:
                raise Refuse("after the merge, %s does not match the record" % f["path"])
            n += 1
    shipped = [t for t, v in record["targets"].items() if v["status"] == "shipped"]
    step("%d files across %d shipped targets match: %s" % (n, len(shipped), ", ".join(sorted(shipped))))


def main():
    if len(sys.argv) != 3:
        print(__doc__)
        return 2
    src, bin_dir = sys.argv[1], os.path.abspath(sys.argv[2])
    print("merge_macos_bundle " + VERSION)
    try:
        rpath = os.path.join(bin_dir, "ffmpeg-licence.json")
        if not os.path.isfile(rpath):
            raise Refuse("%s has no ffmpeg-licence.json; is it formcut's binaries/ folder?" % bin_dir)
        record = json.load(open(rpath))
        with tempfile.TemporaryDirectory() as tmp:
            b = stage(src, tmp)
            info = check_bundle(b, record)
            verification = execute(b, info)
            merge(b, info, verification, bin_dir, record)
        recheck(bin_dir)
    except Refuse as e:
        print("\nREFUSING: %s\nNothing in %s was changed." % (e, bin_dir)
              if "after the merge" not in str(e) else "\nREFUSING: %s" % e)
        return 1
    print("\ndone")
    return 0


if __name__ == "__main__":
    sys.exit(main())
