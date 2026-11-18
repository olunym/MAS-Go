#!/usr/bin/env python3
"""Build the release zip for the Go Minigame submod.

Usage:
    python3 tools/build_release.py

The zip is written to dist/MAS_Go_Minigame-v<version>.zip, together with a
.sha256 file. Players extract it into their MAS folder, so everything inside
starts with game/Submods/MAS_Go_Minigame/.

Before building, the script checks that:
  - every script and asset is present,
  - the bundled GNU Go programs exist and really are a Windows .exe and a
    Linux ELF program (so the wrong file cannot be shipped by accident),
  - the GNU Go license file and the project notices are present,
  - header.rpy has a real author and a version number.

Linux program permissions (0755) are stored in the zip, so they survive
extraction on tools that honor them. The submod also runs chmod itself.
"""
import hashlib
import os
import re
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SUBMOD_NAME = "MAS_Go_Minigame"
SUBMOD_DIR = os.path.join(ROOT, "game", "Submods", SUBMOD_NAME)
ZIP_PREFIX = "game/Submods/" + SUBMOD_NAME + "/"
DIST = os.path.join(ROOT, "dist")

SCRIPTS = [
    "header.rpy", "go_engine.rpy", "go_screen.rpy", "go_skill.rpy",
    "go_dialogue.rpy", "go_dialogue_end.rpy", "go_tutorial.rpy", "go_tutorial2.rpy",
]
ASSET_FILES = (
    ["board_{0}.png".format(n) for n in (9, 13, 19)]
    + ["{0}_{1}.png".format(kind, n)
       for kind in ("stone_black", "stone_white", "ghost", "marker", "dead", "hint")
       for n in (9, 13, 19)]
    + ["hud_panel.png", "hud_panel_d.png", "glow.png", "icon_black.png", "icon_white.png",
       "sfx/stone_player.ogg", "sfx/stone_monika.ogg"]
)
BINARIES = {
    "bin/windows/gnugo.exe": (b"MZ", "a Windows program (.exe)"),
    "bin/linux/gnugo": (b"\x7fELF", "a Linux program (ELF)"),
}
EXECUTABLE = ("bin/linux/gnugo",)
LICENSE_IN_BIN = "bin/GNUGO_LICENSE.txt"
ROOT_DOCS = ["LICENSE", "THIRD_PARTY_NOTICES.md", "README.md"]   # copied into the zip's submod folder
SKIP_EXT = (".rpyc", ".rpyb", ".rpymc", ".log", ".pyc", ".swp")
SKIP_NAMES = ("__pycache__", ".DS_Store", "Thumbs.db", "desktop.ini", ".gitkeep")
FIXED_TIME = (2026, 1, 1, 0, 0, 0)


def fail(errors):
    print("Cannot build the release:")
    for e in errors:
        print("  - " + e)
    sys.exit(1)


def check():
    errors = []
    for name in SCRIPTS:
        if not os.path.isfile(os.path.join(SUBMOD_DIR, name)):
            errors.append("missing script: " + name)
    for name in ASSET_FILES:
        if not os.path.isfile(os.path.join(SUBMOD_DIR, "assets", name)):
            errors.append("missing asset: assets/" + name)
    for name, (magic, label) in BINARIES.items():
        path = os.path.join(SUBMOD_DIR, name)
        if not os.path.isfile(path):
            errors.append("missing GNU Go program: {0}".format(name))
            continue
        with open(path, "rb") as handle:
            head = handle.read(4)
        if not head.startswith(magic):
            errors.append("{0} is not {1}".format(name, label))
        if os.path.getsize(path) < 100 * 1024:
            errors.append("{0} is suspiciously small".format(name))
    if not os.path.isfile(os.path.join(SUBMOD_DIR, LICENSE_IN_BIN)):
        errors.append("missing " + LICENSE_IN_BIN)
    for name in ROOT_DOCS:
        if not os.path.isfile(os.path.join(ROOT, name)):
            errors.append("missing " + name)

    version = None
    header = os.path.join(SUBMOD_DIR, "header.rpy")
    if os.path.isfile(header):
        with open(header, "r", encoding="utf-8") as handle:
            text = handle.read()
        match = re.search(r'version\s*=\s*"(\d+\.\d+\.\d+)"', text)
        if match:
            version = match.group(1)
        else:
            errors.append('header.rpy has no version="X.Y.Z"')
        author = re.search(r'author\s*=\s*"([^"]*)"', text)
        if not author or not author.group(1).strip() or author.group(1) == "YourName":
            errors.append("header.rpy has no real author")
    return errors, version


def collect():
    """List of (zip_name, source_path, mode) in a stable order."""
    entries = []
    for base, dirs, files in os.walk(SUBMOD_DIR):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_NAMES)
        for name in sorted(files):
            if name in SKIP_NAMES or name.endswith(SKIP_EXT):
                continue
            path = os.path.join(base, name)
            rel = os.path.relpath(path, SUBMOD_DIR).replace(os.sep, "/")
            mode = 0o755 if rel in EXECUTABLE else 0o644
            entries.append((ZIP_PREFIX + rel, path, mode))
    for name in ROOT_DOCS:
        entries.append((ZIP_PREFIX + name, os.path.join(ROOT, name), 0o644))
    return entries


def build(version):
    os.makedirs(DIST, exist_ok=True)
    out = os.path.join(DIST, "{0}-v{1}.zip".format(SUBMOD_NAME, version))
    if os.path.exists(out):
        os.remove(out)
    entries = collect()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as archive:
        for zip_name, path, mode in entries:
            info = zipfile.ZipInfo(zip_name, FIXED_TIME)
            info.create_system = 3                      # Unix, so the mode is kept
            info.external_attr = (0o100000 | mode) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            with open(path, "rb") as handle:
                archive.writestr(info, handle.read())
    digest = hashlib.sha256()
    with open(out, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    with open(out + ".sha256", "w") as handle:
        handle.write("{0}  {1}\n".format(digest.hexdigest(), os.path.basename(out)))
    return out, len(entries), digest.hexdigest()


def main():
    errors, version = check()
    if errors:
        fail(errors)
    out, count, digest = build(version)
    size = os.path.getsize(out) / (1024.0 * 1024.0)
    print("Built {0}".format(out))
    print("  version : {0}".format(version))
    print("  files   : {0}".format(count))
    print("  size    : {0:.1f} MB".format(size))
    print("  sha256  : {0}".format(digest))


if __name__ == "__main__":
    main()
