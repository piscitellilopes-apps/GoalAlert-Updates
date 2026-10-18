#!/usr/bin/env python3
"""Build an Enigma2 GoalAlert IPK from versioned sources in GitHub.

Input:
    source/VERSION                 e.g. 6.13.6
    source/GoalAlert/              plugin files (Python, artwork, audio)
Output:
    enigma2-plugin-extensions-goalalert_<version>_all.ipk

Requires Python 3 and the 'ar' program on the GitHub Actions runner.
No device-specific IPTV indexes, logins, or Enigma2 settings are ever packaged.
"""
import io
import os
import pathlib
import re
import subprocess
import tarfile
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "source" / "GoalAlert"
VERSION_FILE = ROOT / "source" / "VERSION"
PREFIX = "usr/lib/enigma2/python/Plugins/Extensions/GoalAlert"
PACKAGE = "enigma2-plugin-extensions-goalalert"

PRIVATE_PATTERNS = (
    re.compile(r"iptv_names_", re.I),
    re.compile(r"\.m3u8?$", re.I),
    re.compile(r"\.log$", re.I),
    re.compile(r"\.pyc$", re.I),
    re.compile(r"(^|/)__pycache__(/|$)", re.I),
    re.compile(r"(^|/)\.env(\.|$)", re.I),
    re.compile(r"(^|/)goalalert_iptv_index", re.I),
)

def tar_bytes(entries):
    """entries: iterable of (path, bytes, mode)"""
    b = io.BytesIO()
    with tarfile.open(fileobj=b, mode="w:xz", format=tarfile.PAX_FORMAT) as tf:
        for name, content, mode in entries:
            info = tarfile.TarInfo(name)
            info.size = len(content)
            info.mode = mode
            info.mtime = 0
            info.uid = 0
            info.gid = 0
            tf.addfile(info, io.BytesIO(content))
    return b.getvalue()

def main():
    version = VERSION_FILE.read_text(encoding="utf-8").strip()
    if not re.fullmatch(r"\d+\.\d+(?:\.\d+){1,3}", version):
        raise SystemExit("Invalid semantic version in source/VERSION")
    if not PLUGIN.is_dir() or not (PLUGIN / "plugin.py").is_file():
        raise SystemExit("Missing source/GoalAlert/plugin.py; refusing partial release")
    entries = []
    for f in sorted(PLUGIN.rglob("*")):
        if not f.is_file():
            continue
        path = f.relative_to(PLUGIN).as_posix()
        if any(rx.search(path) for rx in PRIVATE_PATTERNS):
            raise SystemExit("Unsafe file in source: " + path)
        if f.is_symlink():
            raise SystemExit("Symlinks not allowed: " + path)
        entries.append(("./" + PREFIX + "/" + path, f.read_bytes(), 0o755 if path.endswith(".sh") else 0o644))
    if len(entries) < 12:
        raise SystemExit("Suspiciously incomplete GoalAlert source; build aborted")
    control = (
        f"Package: {PACKAGE}\n"
        f"Version: {version}\nArchitecture: all\n"
        "Maintainer: GoalAlert Local Project\n"
        "Section: extra\nPriority: optional\nDepends: enigma2\n"
        f"Description: GoalAlert {version} online update\n"
    ).encode("utf-8")
    setup = tar_bytes([("./control", control, 0o644)])
    data = tar_bytes(entries)
    output = ROOT / f"{PACKAGE}_{version}_all.ipk"
    with tempfile.TemporaryDirectory() as tmp:
        temp = pathlib.Path(tmp)
        (temp / "debian-binary").write_bytes(b"2.0\n")
        (temp / "control.tar.xz").write_bytes(setup)
        (temp / "data.tar.xz").write_bytes(data)
        subprocess.run(["ar", "q", str(output), "debian-binary", "control.tar.xz", "data.tar.xz"],
                       cwd=str(temp), check=True, stdout=subprocess.DEVNULL)
    print("Built", output, "bytes", output.stat().st_size)

if __name__ == "__main__":
    main()
