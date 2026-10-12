#!/usr/bin/env python3
"""Assemble the hiddriver360 PeerPressure "Softmod Extra".

Shareable Extra (contains no PeerPressure files - this is what releases/CI ship):

    python tools/make-extra.py --release

Personal Extra for your own USB stick, with Aurora support wired up from YOUR PeerPressure
download (its AuroraFixer.xex is kept as AuroraFixer.orig.xex, which our loader runs first):

    python tools/make-extra.py --peerpressure <SoftmodInstaller.zip | BadUpdatePayload | SoftmodData.zip>
                               [--install-into <BadUpdatePayload folder on your USB stick>]

The personal Extra contains a copy of PeerPressure's AuroraFixer.xex - it's for your console only;
don't redistribute it. PeerPressure is grimdoomer's work, not part of this project.

Outputs: dist/release/SoftmodExtras/ or dist/personal/SoftmodExtras/ (HidDriver360/ + the
SoftmodExtras.ini entry). --install-into copies the folder into <BadUpdatePayload>/SoftmodExtras/
and adds the entry to its SoftmodExtras.ini (once), ready for the installer's "Extras Only".

Needs the built loaders (loader/build.sh) and hiddriver/prebuilt/hiddriver.xex.
"""
import argparse
import hashlib
import io
import os
import shutil
import struct
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXTRA_NAME = "HidDriver360"
FIXER_IN_ZIP = "PeerPressure/SideLoading/AuroraFixer.xex"

CREDITS = """hiddriver360 for PeerPressure - credits
=========================================

hiddriver360 - by EinTim23 - https://github.com/EinTim23/hiddriver360
  The controller driver itself: USB HID support, DualShock/DualSense/Switch Pro handling,
  controller mapping, and the XInput integration. GPL-3.0. This project only adds a memory fix
  for running outside DashLaunch, and a loader for PeerPressure.

PeerPressure - by grimdoomer - https://github.com/grimdoomer/Xbox360PeerPressure
  The softmod that makes this possible: its DLL sideloader, the Aurora hook, the removed memory
  protections the loader relies on, and the Softmod Extras installer this package plugs into.
  None of PeerPressure's files are included in this project.

XexTool - by Team Resurgent - https://github.com/Team-Resurgent/XexTool
  Used to build the loaders.

PeerPressure port, loader and packaging - Renae the Raven
  https://github.com/RenaeTheRaven/hiddriver360-PeerPressure
"""

AURORA_HOWTO = """Aurora support
==============

PeerPressure never sideloads .ini DLLs into Aurora (Aurora has no title ID); the only thing it
loads into Aurora is Hdd1:\\PeerPressure\\SideLoading\\AuroraFixer.xex - PeerPressure's own file.
So for Aurora, our chain loader (HidDriver\\AuroraFixer.xex in this folder) has to take that name
and run PeerPressure's original first. This package doesn't ship PeerPressure's file, so set it up
from the copy already on your console:

Automatic (from a PC):
  python install.py install <console-ip>          (over FTP; keeps your console's own fixer)
  python make-extra.py --peerpressure <your PeerPressure download> --install-into <USB>\\BadUpdatePayload

By hand, in Aurora's file manager, in Hdd1:\\PeerPressure\\SideLoading\\:
  1. Rename AuroraFixer.xex to AuroraFixer.orig.xex   (keep it - it's PeerPressure's, and runs first)
  2. Copy HidDriver\\AuroraFixer.xex into SideLoading\\
  Never do step 2 without step 1.
  Undo: delete AuroraFixer.xex and rename AuroraFixer.orig.xex back to AuroraFixer.xex.

The MS dashboard, FreeStyle Dash and XeXMenu need none of this (they use the .ini files).
"""

PEERPRESSURE_NOTICE = """AuroraFixer.orig.xex in this folder is PeerPressure's own AuroraFixer.xex, unmodified, copied
from YOUR PeerPressure download by tools/make-extra.py for use on your own console. It is not part
of hiddriver360-PeerPressure - don't redistribute this Extra. PeerPressure is by grimdoomer:
https://github.com/grimdoomer/Xbox360PeerPressure

Peer Pressure is licensed under Grimdoomer's "You owe me a beer" License v1.0

As long as you retain this notice in all copies and distributions you can do whatever you want
with this stuff. If we ever meet in real life and you've used this stuff you owe me a beer, no
if's and's or but's.

This license is binding under intergalactic law, failing to uphold the terms and conditions will
result in you being labeled as a "leech", "mooch", and "source code grifter" throughout the cosmos.
"""


class Error(Exception):
    pass


def read(path):
    with open(path, "rb") as f:
        return f.read()


def write_text(path, text):
    with open(path, "w", newline="\r\n") as f:
        f.write(text)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def xex_pe_name(data):
    if data[:4] != b"XEX2":
        return None
    for i in range(struct.unpack_from(">I", data, 0x14)[0]):
        key, value = struct.unpack_from(">II", data, 0x18 + 8 * i)
        if key == 0x000183FF:
            size = struct.unpack_from(">I", data, value)[0]
            return data[value + 4:value + size].split(b"\0", 1)[0].decode("ascii", "replace")
    return None


def fixer_from_softmod_data(zip_bytes):
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as z:
        names = {n.replace("\\", "/"): n for n in z.namelist()}
        if FIXER_IN_ZIP not in names:
            raise Error("SoftmodData.zip has no %s" % FIXER_IN_ZIP)
        return z.read(names[FIXER_IN_ZIP])


def find_peerpressure_fixer(src):
    """AuroraFixer.xex bytes from a SoftmodInstaller.zip, BadUpdatePayload dir or SoftmodData.zip."""
    if os.path.isdir(src):
        for cand in (os.path.join(src, "SoftmodData.zip"),
                     os.path.join(src, "BadUpdatePayload", "SoftmodData.zip")):
            if os.path.isfile(cand):
                return fixer_from_softmod_data(read(cand))
        raise Error("no SoftmodData.zip in %s (point at the BadUpdatePayload folder)" % src)
    data = read(src)
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        names = z.namelist()
        if any(n.replace("\\", "/") == FIXER_IN_ZIP for n in names):
            return fixer_from_softmod_data(data)  # this is SoftmodData.zip itself
        inner = [n for n in names if n.replace("\\", "/").endswith("BadUpdatePayload/SoftmodData.zip")]
        if not inner:
            raise Error("%s is neither SoftmodInstaller.zip nor SoftmodData.zip" % src)
        return fixer_from_softmod_data(z.read(inner[0]))


def check_hashes(sums_file, folder):
    for line in open(sums_file):
        digest, name = line.split()
        path = os.path.join(folder, name)
        if not os.path.isfile(path):
            raise Error("%s missing - run loader/build.sh first" % os.path.relpath(path, ROOT))
        if sha(read(path)) != digest:
            print("warning: %s differs from the reference build in %s"
                  % (os.path.relpath(path, ROOT), os.path.relpath(sums_file, ROOT)), file=sys.stderr)


def build(fixer):
    """fixer = PeerPressure's AuroraFixer.xex (personal Extra) or None (shareable release Extra)."""
    if fixer is not None and (xex_pe_name(fixer) or "").lower() != "aurorafixer.exe":
        raise Error("the AuroraFixer.xex found doesn't look like PeerPressure's (PE name %r)"
                    % xex_pe_name(fixer))
    check_hashes(os.path.join(ROOT, "loader", "SHA256SUMS"), os.path.join(ROOT, "loader"))
    check_hashes(os.path.join(ROOT, "hiddriver", "prebuilt", "SHA256SUMS"),
                 os.path.join(ROOT, "hiddriver", "prebuilt"))

    dist = os.path.join(ROOT, "dist", "release" if fixer is None else "personal", "SoftmodExtras")
    out = os.path.join(dist, EXTRA_NAME)
    shutil.rmtree(out, ignore_errors=True)
    os.makedirs(os.path.join(out, "HidDriver"))
    # Everything in this folder is copied into Hdd1:\PeerPressure\SideLoading by the installer.
    hid = os.path.join(out, "HidDriver")
    chain = os.path.join(ROOT, "loader", "AuroraFixer.xex")
    if fixer is None:
        shutil.copy(chain, os.path.join(hid, "AuroraFixer.xex"))  # inactive; see README-AURORA.txt
        write_text(os.path.join(hid, "README-AURORA.txt"), AURORA_HOWTO)
    else:
        shutil.copy(chain, os.path.join(out, "AuroraFixer.xex"))
        with open(os.path.join(out, "AuroraFixer.orig.xex"), "wb") as f:
            f.write(fixer)
        write_text(os.path.join(hid, "PEERPRESSURE-NOTICE.txt"), PEERPRESSURE_NOTICE)
    dash = os.path.join(ROOT, "extra", "dashboards")
    for ini in sorted(os.listdir(dash)):
        shutil.copy(os.path.join(dash, ini), os.path.join(out, ini))
    shutil.copy(os.path.join(ROOT, "loader", "HidLoader.xex"), os.path.join(hid, "HidLoader.xex"))
    shutil.copy(os.path.join(ROOT, "hiddriver", "prebuilt", "hiddriver.xex"), os.path.join(hid, "hiddriver.xex"))
    write_text(os.path.join(hid, "CREDITS.txt"), CREDITS)
    shutil.copy(os.path.join(ROOT, "extra", "SoftmodExtras-entry.ini"),
                os.path.join(dist, "SoftmodExtras-entry.ini"))

    print("built %s (%s)" % (os.path.relpath(out, ROOT),
          "shareable - no PeerPressure files" if fixer is None else "PERSONAL - includes your PeerPressure's AuroraFixer"))
    for r, _, fs in os.walk(out):
        for n in sorted(fs):
            p = os.path.join(r, n)
            print("  %-40s %s" % (os.path.relpath(p, out), sha(read(p))[:12]))
    if fixer is not None:
        print("NOTE: this Extra contains PeerPressure's AuroraFixer.xex from your download - use it on "
              "your own console, don't redistribute it.")
    return out


def install_into(payload, out, personal):
    extras = os.path.join(payload, "SoftmodExtras")
    ini = os.path.join(extras, "SoftmodExtras.ini")
    if not os.path.isfile(ini):
        raise Error("%s not found - point --install-into at the BadUpdatePayload folder" % ini)
    dest = os.path.join(extras, EXTRA_NAME)
    shutil.rmtree(dest, ignore_errors=True)
    shutil.copytree(out, dest)
    text = read(ini).decode("utf-8-sig", "replace")
    if "[%s]" % EXTRA_NAME.lower() in text.lower():
        print("%s already lists [%s]; files updated" % (ini, EXTRA_NAME))
    else:
        entry = read(os.path.join(ROOT, "extra", "SoftmodExtras-entry.ini")).decode()
        entry = "\r\n".join(l for l in entry.replace("\r\n", "\n").split("\n") if not l.startswith(";"))
        with open(ini, "ab") as f:
            f.write(("\r\n" + entry.strip() + "\r\n").encode())
        print("added [%s] to %s" % (EXTRA_NAME, ini))
    print("copied to %s - run the PeerPressure installer and choose Install Extras / Extras Only" % dest)
    if not personal:
        print("note: without --peerpressure this Extra doesn't enable Aurora (see HidDriver/README-AURORA.txt)")


def main():
    ap = argparse.ArgumentParser(description="Build the hiddriver360 PeerPressure Softmod Extra.")
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--release", action="store_true",
                      help="shareable Extra with no PeerPressure files (Aurora set up separately)")
    mode.add_argument("--peerpressure", metavar="DOWNLOAD",
                      help="your SoftmodInstaller.zip / BadUpdatePayload / SoftmodData.zip: personal "
                           "Extra with Aurora support (don't redistribute)")
    ap.add_argument("--install-into", metavar="BadUpdatePayload",
                    help="also copy the Extra into this BadUpdatePayload folder (e.g. on your USB stick)")
    args = ap.parse_args()
    try:
        fixer = None if args.release else find_peerpressure_fixer(args.peerpressure)
        out = build(fixer)
        if args.install_into:
            install_into(args.install_into, out, personal=fixer is not None)
        return 0
    except (Error, OSError, zipfile.BadZipFile) as e:
        print("ERROR: %s" % e, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
