#!/usr/bin/env python3
"""Install hiddriver360 on a PeerPressure Xbox 360 over FTP (alternative to the Softmod Extra).

    python install.py status    <console-ip>
    python install.py install   <console-ip> [--dry-run]
    python install.py uninstall <console-ip> [--dry-run]

Options: --user / --password (FTP login, default xboxftp / xboxftp - Aurora's), --port,
--extra <folder> (the assembled HidDriver360 Extra; default: next to this script, or
dist/SoftmodExtras/HidDriver360 in the repo). Python 3.8+, standard library only.

Installs exactly what the PeerPressure "Softmod Extra" installs, into
Hdd1:\\PeerPressure\\SideLoading\\, with one difference: the console's OWN AuroraFixer.xex is kept as
AuroraFixer.orig.xex (so it always matches the installed PeerPressure version). Also cleans up the
older kernel_patches.bin-based install if it finds one. No other PeerPressure file is touched.

Every changed file is backed up next to this script (backups/<ip>-<time>/), every upload is
verified, and a failed write puts the previous file back. Safe to re-run.

Recovery if the console ever fails to reach the dashboard: power on with the DISC TRAY OPEN
(the loader then skips hiddriver), then run uninstall.
"""
import argparse
import datetime
import ftplib
import hashlib
import io
import os
import struct
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))

PP = "/Hdd1/PeerPressure"
SL = PP + "/SideLoading"
FIXER = SL + "/AuroraFixer.xex"
FIXER_ORIG = SL + "/AuroraFixer.orig.xex"
HID_DIR = SL + "/HidDriver"
HID_FILES = ["HidLoader.xex", "hiddriver.xex", "PEERPRESSURE-NOTICE.txt"]
HID_LOGS = ["aurora-loader.log", "sideload-loader.log"]
INI_MARKER = b"hiddriver360"  # our dashboard INIs say so in their first line

# Older install (kernel_patches.bin record + Hdd1:\PeerPressure\HidDriver\) - migrated away.
KPATCH = PP + "/System/kernel_patches.bin"
LEGACY_PATCH = (0x80078FAC, bytes.fromhex("409AFFD8"))
LEGACY_DIR = PP + "/HidDriver"
LEGACY_FILES = ["hiddriver.xex", "loader.log", "hiddriver_trace.log"]
TERMINATOR = 0xFFFFFFFF

# SHA-256 of every chain loader (AuroraFixer.xex) this project has shipped; the current one is
# always recognised too. XEXes are encrypted, so files are told apart by hash and header.
OUR_LOADER_HASHES = {
    "82711a270658f501c42182b7e4edde49a73e551da53f99dae9cbc31f465fab6a",  # v1
    "1955ca9f8dabdde4ee3bb021bd438a51a9f11042b74b7a654315d5248f37ceda",  # v2 (test)
    "0a3cff1bca31e3ed4f0d057d1e0ec141fea9aeb46952a5d3d9990a9cbae1e289",  # v2b (test)
    "adee418a6c56f33ff6a1615d7de1e902354bd92258df2bb214e8b22b15689204",  # v2c (test)
    "86ed8e6909dd8bc6647e8b9dca06f2f98e1c5cf8c38b9f7ef8e9e400dae69258",  # v3
    "af5a91570a32819cf9007ea971bd7dcb659aea97fc717db425fb0a1095c65806",  # v4
}


class InstallError(Exception):
    pass


# ---- kernel_patches.bin ([u32 addr][u32 len][bytes]..., 0xFFFFFFFF terminator, big-endian),
# only read to remove the record the older install added.

def parse_patches(data):
    records, off = [], 0
    while True:
        if off + 4 > len(data):
            raise InstallError("kernel_patches.bin is truncated (no terminator)")
        addr = struct.unpack_from(">I", data, off)[0]
        if addr == TERMINATOR:
            return records, data[off + 4:]
        if off + 8 > len(data):
            raise InstallError("kernel_patches.bin is truncated")
        length = struct.unpack_from(">I", data, off + 4)[0]
        if length == 0 or off + 8 + length > len(data):
            raise InstallError("kernel_patches.bin has a malformed record at offset %d" % off)
        records.append((addr, data[off + 8:off + 8 + length]))
        off += 8 + length


def without_legacy_patch(data):
    records, trailer = parse_patches(data)
    kept = [r for r in records if r != LEGACY_PATCH]
    if len(kept) == len(records):
        return data, False
    out = bytearray()
    for addr, payload in kept:
        out += struct.pack(">II", addr, len(payload)) + payload
    out += struct.pack(">I", TERMINATOR) + trailer
    return bytes(out), True


# ---- FTP

# Transient failures: timeouts, dropped connections, and FTP 4xx replies. Aurora's FTP server
# occasionally stalls mid-transfer (seen: a STOR left a 0-byte file, then RETR timed out).
TRANSIENT = (OSError, EOFError, ftplib.error_temp, ftplib.error_reply, ftplib.error_proto)
ATTEMPTS = 3


class Console:
    def __init__(self, host, user, password, dry_run, port=21):
        self.host, self.user, self.password, self.port = host, user, password, port
        self.dry_run = dry_run
        self.ftp = None
        try:
            self._connect()
        except TRANSIENT + (ftplib.error_perm,) as e:
            raise InstallError("can't reach the console's FTP at %s: %s (is it on, in Aurora?)"
                               % (host, e))

    def _connect(self):
        self.close()
        self.ftp = ftplib.FTP()
        self.ftp.connect(self.host, self.port, timeout=30)
        self.ftp.login(self.user, self.password)
        self.ftp.set_pasv(True)

    def _retry(self, what, op):
        """Run op() with a fresh connection after each transient failure."""
        for attempt in range(1, ATTEMPTS + 1):
            try:
                return op()
            except TRANSIENT as e:
                if attempt == ATTEMPTS:
                    raise InstallError("%s failed %d times (%s: %s)"
                                       % (what, ATTEMPTS, type(e).__name__, e))
                print("   (FTP hiccup during %s: %s - reconnecting)" % (what, type(e).__name__))
                time.sleep(2)
                try:
                    self._connect()
                except TRANSIENT:
                    pass  # next attempt fails and retries again

    def read(self, path):
        def op():
            buf = io.BytesIO()
            try:
                self.ftp.retrbinary("RETR " + path, buf.write)
            except ftplib.error_perm:
                return None  # no such file
            return buf.getvalue()
        return self._retry("reading " + path, op)

    def exists(self, path):
        return self.read(path) is not None

    def _store_verified(self, path, data):
        for attempt in range(ATTEMPTS):
            self._retry("writing " + path,
                        lambda: self.ftp.storbinary("STOR " + path, io.BytesIO(data)))
            if self.read(path) == data:
                return True
            print("   %s did not verify, retrying..." % path)
        return False

    def write(self, path, data, what, previous=None):
        """Upload and verify. On failure, put `previous` back (if given) and raise."""
        if self.dry_run:
            print("   [dry-run] would write %s (%d bytes)" % (path, len(data)))
            return
        try:
            ok = self._store_verified(path, data)
        except InstallError:
            ok = False
        if ok:
            print("   wrote %s (%d bytes, verified)" % (path, len(data)))
            return
        if previous is None:
            raise InstallError("could not write %s" % path)
        try:
            restored = self._store_verified(path, previous)
        except InstallError:
            restored = False
        if restored:
            raise InstallError("could not write %s; the previous version was put back. Nothing "
                               "is broken - re-run the installer." % path)
        raise InstallError("could not write %s AND could not put the previous version back. DO "
                           "NOT REBOOT the console: re-run this command, or upload the copy from "
                           "the backups folder to %s by FTP." % (path, path))

    def delete(self, path):
        if self.dry_run:
            print("   [dry-run] would delete %s" % path)
            return

        def op():
            try:
                self.ftp.delete(path)
                return True
            except ftplib.error_perm:
                return False  # already gone
        if self._retry("deleting " + path, op):
            print("   deleted %s" % path)

    def mkdir(self, path):
        if self.dry_run:
            return

        def op():
            try:
                self.ftp.mkd(path)
            except ftplib.error_perm:
                pass  # already exists
        self._retry("creating " + path, op)

    def rmdir(self, path):
        if self.dry_run:
            return

        def op():
            try:
                self.ftp.rmd(path)
            except ftplib.error_perm:
                pass  # not empty or already gone
        self._retry("removing " + path, op)

    def close(self):
        if self.ftp is None:
            return
        try:
            self.ftp.quit()
        except ftplib.all_errors + (OSError, EOFError):
            try:
                self.ftp.close()
            except OSError:
                pass
        self.ftp = None


class Backup:
    def __init__(self, host, dry_run):
        stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        base = os.path.join(HERE, "backups", "%s-%s" % (host.replace(":", "_"), stamp))
        self.dir, n = base, 1
        while os.path.exists(self.dir):  # never overwrite an earlier backup
            n += 1
            self.dir = "%s-%d" % (base, n)
        self.dry_run = dry_run
        self.saved = False

    def save(self, console_path, data):
        if self.dry_run or data is None:
            return
        os.makedirs(self.dir, exist_ok=True)
        name = console_path.strip("/").replace("/", "_")  # keeps same-named files apart
        with open(os.path.join(self.dir, name), "wb") as f:
            f.write(data)
        self.saved = True


# ---- payload / classification

def sha(data):
    return hashlib.sha256(data).hexdigest()[:12] if data is not None else "-"


def find_extra(path):
    cands = [path] if path else [os.path.join(HERE, "HidDriver360"),
                                 os.path.join(os.path.dirname(HERE), "dist", "SoftmodExtras", "HidDriver360")]
    for cand in cands:
        if cand and os.path.isfile(os.path.join(cand, "AuroraFixer.xex")):
            return cand
    raise InstallError("HidDriver360 Extra folder not found - build it with tools/make-extra.py "
                       "or pass --extra <folder>")


class Payload:
    """The assembled Extra: the files that end up in Hdd1:\\PeerPressure\\SideLoading."""
    def __init__(self, folder):
        def rd(*p):
            with open(os.path.join(folder, *p), "rb") as f:
                return f.read()
        self.loader = rd("AuroraFixer.xex")
        self.bundled_orig = rd("AuroraFixer.orig.xex")
        self.hid = {n: rd("HidDriver", n) for n in HID_FILES}
        self.inis = {n: rd(n) for n in sorted(os.listdir(folder)) if n.lower().endswith(".ini")}


def xex_original_pe_name(data):
    """The 'original PE name' from a XEX2 header (unencrypted), or None."""
    if data is None or len(data) < 0x18 or data[:4] != b"XEX2":
        return None
    for i in range(min(struct.unpack_from(">I", data, 0x14)[0], 64)):
        key, value = struct.unpack_from(">II", data, 0x18 + 8 * i)
        if key == 0x000183FF and value + 4 < len(data):
            size = struct.unpack_from(">I", data, value)[0]
            return data[value + 4:value + min(size, 256)].split(b"\0", 1)[0].decode("ascii", "replace")
    return None


def classify_fixer(data, payload):
    """'ours', 'peerpressure', 'unknown' or 'missing' for an AuroraFixer.xex."""
    if data is None:
        return "missing"
    if data == payload.loader or hashlib.sha256(data).hexdigest() in OUR_LOADER_HASHES:
        return "ours"
    if (xex_original_pe_name(data) or "").lower().startswith("aurorafixer"):
        return "peerpressure"
    return "unknown"


# ---- commands

def require_peerpressure(con):
    if con.read(PP + "/System/Config.ini") is None:
        raise InstallError("Hdd1:\\PeerPressure\\System\\Config.ini not found - is PeerPressure "
                           "installed on this console's hard drive?")


def status(con, payload):
    fixer, orig = con.read(FIXER), con.read(FIXER_ORIG)
    kind = classify_fixer(fixer, payload)
    label = {"ours": "hiddriver chain loader" + ("" if fixer == payload.loader else " (older version)"),
             "peerpressure": "PeerPressure original", "unknown": "UNRECOGNISED", "missing": "missing"}
    print("AuroraFixer.xex       : %s (sha %s)" % (label[kind], sha(fixer)))
    print("AuroraFixer.orig.xex  : %s" % ("missing" if orig is None else "present (sha %s)" % sha(orig)))
    for n, want in payload.hid.items():
        have = con.read(HID_DIR + "/" + n)
        print("%-22s: %s" % ("HidDriver\\" + n, "missing" if have is None else
              "up to date" if have == want else "different (sha %s)" % sha(have)))
    for n, want in payload.inis.items():
        have = con.read(SL + "/" + n)
        print("%-22s: %s" % (n, "missing" if have is None else "up to date" if have == want else "different"))
    kp = con.read(KPATCH)
    if kp is not None and LEGACY_PATCH in parse_patches(kp)[0]:
        print("older install         : kernel_patches.bin has the old hiddriver record (install removes it)")
    if con.exists(LEGACY_DIR + "/hiddriver.xex"):
        print("older install         : Hdd1:\\PeerPressure\\HidDriver\\hiddriver.xex (install removes it)")
    for n in HID_LOGS:
        log = con.read(HID_DIR + "/" + n)
        lines = [l for l in (log or b"").decode("ascii", "replace").splitlines() if l.strip()]
        if lines:
            print("%-22s: %s" % (n, lines[-1]))


def remove_legacy(con, backup):
    kp = con.read(KPATCH)
    if kp is not None:
        new_kp, changed = without_legacy_patch(kp)
        if changed:
            print("   removing the old hiddriver record from kernel_patches.bin")
            backup.save(KPATCH, kp)
            con.write(KPATCH, new_kp, "kernel_patches.bin", previous=kp)
    for n in LEGACY_FILES:
        path = LEGACY_DIR + "/" + n
        data = con.read(path)
        if data is not None:
            backup.save(path, data)
            con.delete(path)


def install(con, backup, payload):
    require_peerpressure(con)
    # Check everything before writing anything, so a refusal never leaves a half install.
    fixer, orig = con.read(FIXER), con.read(FIXER_ORIG)
    kind = classify_fixer(fixer, payload)
    if kind == "unknown":
        raise InstallError("AuroraFixer.xex is neither PeerPressure's fixer nor this project's loader "
                           "(sha %s) - not touching it." % sha(fixer))
    kp = con.read(KPATCH)
    if kp is not None:
        parse_patches(kp)  # refuse early on a malformed file

    print("1. hiddriver + loader")
    con.mkdir(HID_DIR)
    for n, want in payload.hid.items():
        path = HID_DIR + "/" + n
        have = con.read(path)
        if have == want:
            print("   %s up to date" % n)
        else:
            backup.save(path, have)
            con.write(path, want, n, previous=have)

    print("2. dashboard sideload INIs")
    for n, want in payload.inis.items():
        path = SL + "/" + n
        have = con.read(path)
        if have == want:
            print("   %s up to date" % n)
        else:
            backup.save(path, have)
            con.write(path, want, n, previous=have)

    print("3. Aurora (AuroraFixer chain loader)")
    if kind == "peerpressure":
        if orig is not None and orig != fixer:
            backup.save(FIXER_ORIG, orig)
        backup.save(FIXER, fixer)
        con.write(FIXER_ORIG, fixer, "AuroraFixer.orig.xex", previous=orig)  # the console's own fixer
    elif orig is None:
        print("   no PeerPressure AuroraFixer on the console - using the one bundled with the Extra")
        con.write(FIXER_ORIG, payload.bundled_orig, "AuroraFixer.orig.xex")
    if fixer == payload.loader:
        print("   loader up to date")
    else:
        con.write(FIXER, payload.loader, "AuroraFixer.xex", previous=fixer)

    print("4. cleanup of the older install")
    remove_legacy(con, backup)


def uninstall(con, backup, payload):
    require_peerpressure(con)
    fixer, orig = con.read(FIXER), con.read(FIXER_ORIG)
    kind = classify_fixer(fixer, payload)
    if kind == "ours" and orig is None:
        raise InstallError("AuroraFixer.orig.xex is missing, can't restore PeerPressure's fixer. "
                           "Copy AuroraFixer.xex from your PeerPressure download to "
                           "Hdd1:\\PeerPressure\\SideLoading\\AuroraFixer.orig.xex, then re-run.")
    kp = con.read(KPATCH)
    if kp is not None:
        parse_patches(kp)

    print("1. Aurora")
    if kind != "ours":
        print("   AuroraFixer.xex is not ours - left alone")
    else:
        backup.save(FIXER, fixer)
        con.write(FIXER, orig, "AuroraFixer.xex", previous=fixer)
        con.delete(FIXER_ORIG)

    print("2. dashboard sideload INIs")
    for n in payload.inis:
        have = con.read(SL + "/" + n)
        if have is not None and INI_MARKER in have:
            backup.save(SL + "/" + n, have)
            con.delete(SL + "/" + n)

    print("3. hiddriver + loader")
    for n in HID_FILES + HID_LOGS:
        path = HID_DIR + "/" + n
        data = con.read(path)
        if data is not None:
            if n in HID_FILES:
                backup.save(path, data)
            con.delete(path)
    con.rmdir(HID_DIR)

    print("4. cleanup of the older install")
    remove_legacy(con, backup)
    print("   (controller mappings in Hdd1:\\hiddriver.json are kept)")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("command", choices=["status", "install", "uninstall"])
    ap.add_argument("host", help="console IP address")
    ap.add_argument("--user", default="xboxftp")
    ap.add_argument("--password", default="xboxftp")
    ap.add_argument("--port", type=int, default=21)
    ap.add_argument("--extra", help="the HidDriver360 Extra folder (default: auto-detect)")
    ap.add_argument("--dry-run", action="store_true", help="show what would change, write nothing")
    args = ap.parse_args()

    con = None
    try:
        payload = Payload(find_extra(args.extra))
        con = Console(args.host, args.user, args.password, args.dry_run, args.port)
        if args.command == "status":
            status(con, payload)
            return 0
        backup = Backup(args.host, args.dry_run)
        (install if args.command == "install" else uninstall)(con, backup, payload)
        if backup.saved:
            print("backups saved in %s" % backup.dir)
        if args.dry_run:
            print("dry run: nothing was changed.")
        elif args.command == "install":
            print("Done. Reboot the console (tray closed) with a controller plugged in.")
        else:
            print("Done. Reboot the console.")
        return 0
    except InstallError as e:
        print("ERROR: %s" % e, file=sys.stderr)
        return 1
    except Exception as e:  # never leave the user with just a traceback
        print("ERROR: unexpected %s: %s" % (type(e).__name__, e), file=sys.stderr)
        print("Run 'python install.py status <ip>' to check the console before rebooting.",
              file=sys.stderr)
        return 1
    finally:
        if con:
            con.close()


if __name__ == "__main__":
    sys.exit(main())
