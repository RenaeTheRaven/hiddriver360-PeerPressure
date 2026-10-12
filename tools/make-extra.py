#!/usr/bin/env python3
"""Assemble the hiddriver360 PeerPressure "Softmod Extra".

    python tools/make-extra.py --peerpressure <PeerPressure download> [--install-into <BadUpdatePayload>]

<PeerPressure download> is any of: SoftmodInstaller.zip, an extracted BadUpdatePayload folder, or
its SoftmodData.zip. PeerPressure's own AuroraFixer.xex is taken from it (and stored as
AuroraFixer.orig.xex, which our loader runs first), so the Extra always matches the PeerPressure
version you install it with.

Output: dist/SoftmodExtras/HidDriver360/ plus dist/SoftmodExtras/SoftmodExtras-entry.ini.
With --install-into, the folder is copied into <BadUpdatePayload>/SoftmodExtras/ and the entry is
added to its SoftmodExtras.ini (once), ready for the installer's "Extras Only" option.

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
DIST = os.path.join(ROOT, "dist", "SoftmodExtras")
EXTRA_NAME = "HidDriver360"
FIXER_IN_ZIP = "PeerPressure/SideLoading/AuroraFixer.xex"

PEERPRESSURE_NOTICE = """AuroraFixer.orig.xex is PeerPressure's own AuroraFixer.xex, unmodified, copied from the
PeerPressure release this Extra was built with. PeerPressure: https://github.com/grimdoomer/Xbox360PeerPressure

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
    if (xex_pe_name(fixer) or "").lower() != "aurorafixer.exe":
        raise Error("the AuroraFixer.xex found doesn't look like PeerPressure's (PE name %r)"
                    % xex_pe_name(fixer))
    check_hashes(os.path.join(ROOT, "loader", "SHA256SUMS"), os.path.join(ROOT, "loader"))
    check_hashes(os.path.join(ROOT, "hiddriver", "prebuilt", "SHA256SUMS"),
                 os.path.join(ROOT, "hiddriver", "prebuilt"))

    out = os.path.join(DIST, EXTRA_NAME)
    shutil.rmtree(out, ignore_errors=True)
    os.makedirs(os.path.join(out, "HidDriver"))
    # Everything in this folder is copied into Hdd1:\PeerPressure\SideLoading by the installer.
    shutil.copy(os.path.join(ROOT, "loader", "AuroraFixer.xex"), os.path.join(out, "AuroraFixer.xex"))
    with open(os.path.join(out, "AuroraFixer.orig.xex"), "wb") as f:
        f.write(fixer)
    dash = os.path.join(ROOT, "extra", "dashboards")
    for ini in sorted(os.listdir(dash)):
        shutil.copy(os.path.join(dash, ini), os.path.join(out, ini))
    shutil.copy(os.path.join(ROOT, "loader", "HidLoader.xex"), os.path.join(out, "HidDriver", "HidLoader.xex"))
    shutil.copy(os.path.join(ROOT, "hiddriver", "prebuilt", "hiddriver.xex"),
                os.path.join(out, "HidDriver", "hiddriver.xex"))
    with open(os.path.join(out, "HidDriver", "PEERPRESSURE-NOTICE.txt"), "w", newline="\r\n") as f:
        f.write(PEERPRESSURE_NOTICE)
    shutil.copy(os.path.join(ROOT, "extra", "SoftmodExtras-entry.ini"),
                os.path.join(DIST, "SoftmodExtras-entry.ini"))
    print("built %s" % os.path.relpath(out, ROOT))
    for r, _, fs in os.walk(out):
        for n in sorted(fs):
            p = os.path.join(r, n)
            print("  %-40s %s" % (os.path.relpath(p, out), sha(read(p))[:12]))
    print("  (AuroraFixer.orig.xex = PeerPressure's AuroraFixer, sha %s)" % sha(fixer)[:12])
    return out


def install_into(payload, out):
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
    print("copied to %s - run the PeerPressure installer and choose Install Extras / Extras Only"
          % dest)


def main():
    ap = argparse.ArgumentParser(description="Build the hiddriver360 PeerPressure Softmod Extra.")
    ap.add_argument("--peerpressure", required=True,
                    help="SoftmodInstaller.zip, BadUpdatePayload folder, or SoftmodData.zip")
    ap.add_argument("--install-into", metavar="BadUpdatePayload",
                    help="also copy the Extra into this BadUpdatePayload folder (e.g. on your USB stick)")
    args = ap.parse_args()
    try:
        out = build(find_peerpressure_fixer(args.peerpressure))
        if args.install_into:
            install_into(args.install_into, out)
        return 0
    except (Error, OSError, zipfile.BadZipFile) as e:
        print("ERROR: %s" % e, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
