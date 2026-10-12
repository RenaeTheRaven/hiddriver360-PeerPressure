"""Tests for tools/install.py: install/uninstall logic and FTP fault handling, against an in-memory
fake FTP server (the real Console class is exercised). Self-contained: synthetic fixtures only.

    python -m unittest discover -s tests
"""
import contextlib
import ftplib
import io
import os
import struct
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))
import install as I  # noqa: E402

I.time.sleep = lambda s: None


def fake_xex(pe_name, filler=b""):
    """Minimal XEX2 header carrying an 'original PE name' (0x183FF) optional header."""
    name = pe_name.encode() + b"\0"
    off = 0x18 + 8
    hdr = bytearray(b"XEX2" + b"\0" * 0x10 + struct.pack(">I", 1))
    hdr += struct.pack(">II", 0x000183FF, off)
    hdr += struct.pack(">I", 4 + len(name)) + name
    return bytes(hdr) + filler


def kpatch(records):
    out = b"".join(struct.pack(">II", a, len(p)) + p for a, p in records)
    return out + struct.pack(">I", 0xFFFFFFFF)


PP_FIXER = fake_xex("AuroraFixer.exe", b"pp-fixer-v1")
PP_FIXER_NEW = fake_xex("AuroraFixer.exe", b"pp-fixer-v2")
STOCK_RECORDS = [(0x8009D660, bytes.fromhex("48000068")), (0x800D8748, bytes.fromhex("386000014e800020"))]
KP_STOCK = kpatch(STOCK_RECORDS)
KP_LEGACY = kpatch(STOCK_RECORDS + [I.LEGACY_PATCH])
CONFIG = b"[Dashboard]\r\n"

FILES = {}
FAULTS = []  # (op, path substring, kind)


class FakeFTP:
    def connect(self, *a, **k): pass
    def login(self, *a): pass
    def set_pasv(self, v): pass
    def quit(self): pass
    def close(self): pass

    def _fault(self, op, path):
        for i, (fop, sub, kind) in enumerate(FAULTS):
            if fop == op and sub in path:
                del FAULTS[i]
                return kind
        return None

    def storbinary(self, cmd, fp):
        path = cmd[5:]
        f = self._fault("STOR", path)
        if f == "zero":  # what Aurora's FTP did: truncated file, then a stalled transfer
            FILES[path] = b""
            raise TimeoutError("timed out")
        FILES[path] = fp.read()

    def retrbinary(self, cmd, cb):
        path = cmd[5:]
        if self._fault("RETR", path) == "timeout":
            raise TimeoutError("timed out")
        if path not in FILES:
            raise ftplib.error_perm("550 not found")
        cb(FILES[path])

    def delete(self, path):
        if path not in FILES:
            raise ftplib.error_perm("550")
        del FILES[path]

    def mkd(self, path): pass
    def rmd(self, path): pass


I.ftplib.FTP = FakeFTP


class NoBackup:
    saved = False
    def save(self, *a): pass


def make_payload(tmp):
    root = os.path.join(tmp, "HidDriver360")
    os.makedirs(os.path.join(root, "HidDriver"))
    files = {"AuroraFixer.xex": fake_xex("HidLoader", b"chain-v-current"),
             "AuroraFixer.orig.xex": PP_FIXER,
             "fffe07d1.ini": b"; hiddriver360: MS dashboard\r\n[DllConfig]\r\n",
             "f5d20000.ini": b"; hiddriver360: FSD\r\n[DllConfig]\r\n",
             "HidDriver/HidLoader.xex": b"sideload-dll",
             "HidDriver/hiddriver.xex": b"hiddriver",
             "HidDriver/PEERPRESSURE-NOTICE.txt": b"notice"}
    for name, data in files.items():
        with open(os.path.join(root, *name.split("/")), "wb") as f:
            f.write(data)
    return I.Payload(root)


def stock_console():
    return {I.PP + "/System/Config.ini": CONFIG, I.KPATCH: KP_STOCK, I.FIXER: PP_FIXER}


class Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.payload = make_payload(self._tmp.name)
        FILES.clear()
        FAULTS.clear()

    def tearDown(self):
        self._tmp.cleanup()

    def run_cmd(self, fn, dry_run=False):
        con = I.Console("x", "u", "p", dry_run)
        with contextlib.redirect_stdout(io.StringIO()):
            fn(con, NoBackup(), self.payload)

    def assert_installed(self, orig=PP_FIXER):
        self.assertEqual(FILES[I.FIXER], self.payload.loader)
        self.assertEqual(FILES[I.FIXER_ORIG], orig)
        for n, data in self.payload.hid.items():
            self.assertEqual(FILES[I.HID_DIR + "/" + n], data)
        for n, data in self.payload.inis.items():
            self.assertEqual(FILES[I.SL + "/" + n], data)
        self.assertEqual(FILES[I.KPATCH], KP_STOCK)  # never patched by this version


class InstallTests(Base):
    def test_fresh_install_and_rerun(self):
        FILES.update(stock_console())
        self.run_cmd(I.install)
        self.assert_installed()
        snapshot = dict(FILES)
        self.run_cmd(I.install)
        self.assertEqual(FILES, snapshot)

    def test_uninstall_restores_stock_exactly(self):
        FILES.update(stock_console())
        FILES[I.SL + "/SideLoad.ini"] = b"pp's own"
        before = dict(FILES)
        self.run_cmd(I.install)
        FILES[I.HID_DIR + "/aurora-loader.log"] = b"log"
        self.run_cmd(I.uninstall)
        self.assertEqual(FILES, before)

    def test_uninstall_leaves_foreign_ini(self):
        FILES.update(stock_console())
        self.run_cmd(I.install)
        FILES[I.SL + "/f5d20000.ini"] = b"[DllConfig]\r\n; somebody else's FSD plugin\r\n"
        self.run_cmd(I.uninstall)
        self.assertIn(I.SL + "/f5d20000.ini", FILES)

    def test_dry_run_changes_nothing(self):
        FILES.update(stock_console())
        before = dict(FILES)
        self.run_cmd(I.install, dry_run=True)
        self.assertEqual(FILES, before)

    def test_migrates_legacy_install(self):
        FILES.update(stock_console())
        FILES[I.KPATCH] = KP_LEGACY
        FILES[I.FIXER] = fake_xex("x", b"old")  # stand-in; mark as a known old loader below
        I.OUR_LOADER_HASHES.add(I.hashlib.sha256(FILES[I.FIXER]).hexdigest())
        FILES[I.FIXER_ORIG] = PP_FIXER
        FILES[I.LEGACY_DIR + "/hiddriver.xex"] = b"old hiddriver"
        FILES[I.LEGACY_DIR + "/loader.log"] = b"old log"
        self.run_cmd(I.install)
        self.assert_installed()
        self.assertNotIn(I.LEGACY_DIR + "/hiddriver.xex", FILES)
        self.assertNotIn(I.LEGACY_DIR + "/loader.log", FILES)

    def test_peerpressure_update_refreshes_orig(self):
        FILES.update(stock_console())
        self.run_cmd(I.install)
        FILES[I.FIXER] = PP_FIXER_NEW  # a PeerPressure update restored its (newer) fixer
        self.run_cmd(I.install)
        self.assert_installed(orig=PP_FIXER_NEW)

    def test_unknown_fixer_refused_before_any_write(self):
        FILES.update(stock_console())
        FILES[I.FIXER] = b"something else"
        before = dict(FILES)
        with self.assertRaises(I.InstallError):
            self.run_cmd(I.install)
        self.assertEqual(FILES, before)

    def test_malformed_kernel_patches_refused_before_any_write(self):
        FILES.update(stock_console())
        FILES[I.KPATCH] = KP_STOCK[:-4]
        before = dict(FILES)
        with self.assertRaises(I.InstallError):
            self.run_cmd(I.install)
        self.assertEqual(FILES, before)

    def test_not_peerpressure_refused(self):
        FILES[I.FIXER] = PP_FIXER
        with self.assertRaises(I.InstallError):
            self.run_cmd(I.install)


class FaultTests(Base):
    def test_transient_stall_recovers(self):
        FILES.update(stock_console())
        FAULTS[:] = [("STOR", "AuroraFixer.xex", "zero"), ("RETR", "AuroraFixer.xex", "timeout"),
                     ("RETR", "hiddriver.xex", "timeout")]
        self.run_cmd(I.install)
        self.assert_installed()

    def test_persistent_failure_puts_previous_back(self):
        FILES.update(stock_console())
        FAULTS[:] = [("STOR", "SideLoading/AuroraFixer.xex", "zero")] * 3
        with self.assertRaises(I.InstallError) as cm:
            self.run_cmd(I.install)
        self.assertIn("previous version was put back", str(cm.exception))
        self.assertEqual(FILES[I.FIXER], PP_FIXER)

    def test_write_and_restore_fail_says_do_not_reboot(self):
        FILES.update(stock_console())
        FAULTS[:] = [("STOR", "SideLoading/AuroraFixer.xex", "zero")] * 30
        with self.assertRaises(I.InstallError) as cm:
            self.run_cmd(I.install)
        self.assertIn("DO NOT REBOOT", str(cm.exception))

    def test_legacy_kpatch_rewrite_failure_restores_it(self):
        FILES.update(stock_console())
        FILES[I.KPATCH] = KP_LEGACY
        FAULTS[:] = [("STOR", "kernel_patches", "zero")] * 3
        with self.assertRaises(I.InstallError):
            self.run_cmd(I.install)
        self.assertEqual(FILES[I.KPATCH], KP_LEGACY)


if __name__ == "__main__":
    unittest.main()
