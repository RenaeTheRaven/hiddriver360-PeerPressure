#!/bin/bash
# Builds the two loader DLLs from HidLoader.S:
#   HidLoader.xex   - PeerPressure ini-sideload DLL (dashboards with a title ID)
#   AuroraFixer.xex - (-DCHAIN) stands in for PeerPressure's AuroraFixer.xex (Aurora)
# Needs clang, ld.lld and XexTool (https://github.com/Team-Resurgent/XexTool) - set XEXTOOL if
# it isn't on PATH. stubs.s/stubs.json were generated with:
#   XexTool genstubs --xdk <hiddriver360>/hiddriver/xkelib --names XexLoadImage,XexGetModuleHandle,ObCreateSymbolicLink,NtCreateFile,NtWriteFile,NtClose,HalSendSMCMessage -o stubs.s --manifest stubs.json
set -e
cd "$(dirname "$0")"
XT=${XEXTOOL:-XexTool}
CC="clang --target=powerpc-unknown-none -mcpu=pwr5 -mbig-endian"
$CC -c stubs.s -o stubs.o
for v in HidLoader:"" AuroraFixer:"-DCHAIN"; do
  name=${v%%:*}; def=${v#*:}
  $CC $def -c HidLoader.S -o $name.o
  ld.lld -m elf32ppc -T link.ld $name.o stubs.o -o $name.elf
  $XT pack $name.elf -o $name.unsigned.xex --import-manifest stubs.json
  # pack emits an EXE title module (flags 0x1) with a placeholder execution ID and TLS header.
  # Make it a title DLL (0x9) and drop those two headers (PeerPressure loads title DLLs).
  python3 -I -c "
import struct,sys
f=open(sys.argv[1],'r+b');d=bytearray(f.read())
assert d[4:8]==b'\0\0\0\x01';d[4:8]=b'\0\0\0\x09'
n=struct.unpack_from('>I',d,0x14)[0]
e=[struct.unpack_from('>II',d,0x18+8*i) for i in range(n)]
k=[x for x in e if x[0] not in (0x40006,0x20104)]
assert len(k)==n-2
struct.pack_into('>I',d,0x14,len(k))
for i,x in enumerate(k+[(0,0)]*2): struct.pack_into('>II',d,0x18+8*i,*x)
f.seek(0);f.write(d)" $name.unsigned.xex
  # devkit-sign and encrypt (retail kernels reject unencrypted images)
  $XT -m d -e e -o $name.xex $name.unsigned.xex
  rm -f $name.unsigned.xex
done
