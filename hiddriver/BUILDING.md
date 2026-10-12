# Building hiddriver.xex

`prebuilt/hiddriver.xex` is [hiddriver360](https://github.com/EinTim23/hiddriver360) by
EinTim23 (GPL-3.0) at upstream commit
[`6159866`](https://github.com/EinTim23/hiddriver360/commit/6159866) (v0.6-beta master) with
[`0001-Keep-USB-transfer-state-out-of-the-loader-s-process-.patch`](0001-Keep-USB-transfer-state-out-of-the-loader-s-process-.patch)
applied. Building it needs an Xbox 360 XDK, which can't be distributed (so it can't be built in CI).

```
git clone https://github.com/EinTim23/hiddriver360 && cd hiddriver360
git checkout 6159866
git am ../hiddriver/0001-Keep-USB-transfer-state-out-of-the-loader-s-process-.patch
```

Then build `hiddriver.vcxproj` (Release) with the XDK's Visual Studio integration, or by hand:

```
cl.exe /c /nologo /DNDEBUG /D_XBOX /DLTCG /MT /Ox /GS-  main.cpp mapping.cpp hid_parser.cpp Detours.cpp
link.exe /nologo /DLL /INCREMENTAL:NO /DEBUG:NONE /PDB:NONE /BASE:0x81F00000 ^
    /XEXCONFIG:xex.xml /PE:hiddriver.exe /OUT:hiddriver.xex ^
    main.obj mapping.obj hid_parser.obj Detours.obj xapilib.lib xkelib.lib xboxkrnl.lib libcMT.lib
XexTool -r m -m d -c c -e e -o hiddriver.allmedia.xex hiddriver.xex
```

- `INCLUDE`: the source folder, `xkelib`, and the XDK's `include\xbox`.
- **`xapilib.lib` first**: with a newer XDK's `xkelib`, the Win32 helpers would otherwise be
  imported from xam — including `GetProcessHeap` (xam ordinal 2002), which the 17559 xam doesn't
  export (`XexLoadImage` → `C0000156`).
- **`/XEXCONFIG:xex.xml`** makes link's automatic imagexex step build a *system* DLL at
  `0x81F00000`; without it you get `IM1067` / `LNK1500`.
- The last step re-signs for hard-drive loading (the release is System-Flash-only).

The shipped binary was built with XDK 21256 (TechPreview Jul12 compiler) under Wine; the expected
SHA-256 is in [`prebuilt/SHA256SUMS`](prebuilt/SHA256SUMS). A different XDK or compiler will produce
a different (but equivalent) binary.
