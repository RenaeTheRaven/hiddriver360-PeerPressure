# HidLoader - tiny title DLL that loads hiddriver360 (a system DLL) under PeerPressure.
#
# Built twice from this file:
#   HidLoader.xex    - sideloaded by PeerPressure into dashboards that have a title ID (MS
#                      dashboard, FreeStyle, XeXMenu, ...) via SideLoading\<title id>.ini.
#   AuroraFixer.xex  - (-DCHAIN) Aurora has no title ID, so PeerPressure never ini-sideloads
#                      into it; its only hook is SideLoading\AuroraFixer.xex. This variant takes
#                      that name, loads PeerPressure's real fixer (shipped alongside as
#                      AuroraFixer.orig.xex) first, then hiddriver.
# Both run before the dashboard's entry point.
#
# hiddriver is a system module, and the kernel's module loader refuses to load one from a
# title context (STATUS_ACCESS_DENIED) with a single branch at 0x80078FAC (kernel 17559).
# PeerPressure removes memory protections, so this loader flips that branch to the success
# path just for the duration of the load and then puts the original instruction back. It
# checks the instruction first and does nothing on an unexpected kernel. No PeerPressure
# file is modified, so uninstalling is just deleting the files.
#
# With the disc tray open it does nothing (recovery path).
#
# Every step is logged with its status to Hdd1:\PeerPressure\SideLoading\HidDriver\loader.log
# (recreated on every boot, opened/closed per line so it survives a hang).
#
# Written by hand against the Xbox 360 calling convention (args r3-r10, 9th+ args from
# 0x54(r1), LR saved at -8(r1), r2/r13 untouched) so there is no compiler ABI mismatch.

    .set GATE_ORIGINAL_HI, 0x409A       # bne cr6, +0x2C   -> STATUS_ACCESS_DENIED path
    .set GATE_ORIGINAL_LO, 0x002C
    .set GATE_PATCHED_LO,  0xFFD8       # bne cr6, -0x28   -> success path

    .section .text,"ax"
    .globl DllMain
DllMain:
    mflr    12
    stw     12, -8(1)
    stwu    1, -0x100(1)

    cmpwi   4, 1                    # DLL_PROCESS_ATTACH only
    bne     .Ldone

    lis     3, logEntry@ha
    addi    3, 3, logEntry@l
    bl      LogLine

#ifdef CHAIN
    # PeerPressure's real AuroraFixer first, exactly as PeerPressure would load it.
    lis     3, pathFixer@ha
    addi    3, 3, pathFixer@l
    li      4, 9                    # title DLL
    li      5, 0
    addi    6, 1, 0x80
    bl      XexLoadImage
    mr      4, 3
    lis     3, logFixer@ha
    addi    3, 3, logFixer@l
    bl      LogLine
#endif

    # HDD: -> \Device\Harddisk0\Partition1 (hiddriver keeps its mappings in HDD:\hiddriver.json).
    lis     3, strLink@ha
    addi    3, 3, strLink@l
    lis     4, strDevice@ha
    addi    4, 4, strDevice@l
    bl      ObCreateSymbolicLink
    mr      4, 3
    lis     3, logLink@ha
    addi    3, 3, logLink@l
    bl      LogLine

    # Only load hiddriver once; it is a system module and persists across titles.
    lis     3, nameHid@ha
    addi    3, 3, nameHid@l
    addi    4, 1, 0x84
    bl      XexGetModuleHandle      # r3 = 0 only if hiddriver is ALREADY loaded
    cmpwi   3, 0
    bne     1f
    li      4, 0
    lis     3, logLoaded@ha
    addi    3, 3, logLoaded@l
    bl      LogLine
    b       .Ldone
1:
    bl      IsTrayOpen
    stw     3, 0x90(1)
    mr      4, 3
    lis     3, logTray@ha
    addi    3, 3, logTray@l
    bl      LogLine
    lwz     3, 0x90(1)
    cmpwi   3, 0
    bne     .Ldone

    # Check the module-loader gate before touching it.
    lis     9, 0x8007
    ori     9, 9, 0x8FAC
    lwz     4, 0(9)
    stw     4, 0x98(1)
    lis     3, logGate@ha
    addi    3, 3, logGate@l
    bl      LogLine
    li      11, 0
    stw     11, 0x94(1)             # 1 = we patched the gate and must restore it
    lwz     4, 0x98(1)
    lis     10, GATE_ORIGINAL_HI
    ori     10, 10, GATE_ORIGINAL_LO
    cmplw   4, 10
    beq     .Lpatch
    lis     10, GATE_ORIGINAL_HI
    ori     10, 10, GATE_PATCHED_LO
    cmplw   4, 10
    beq     .Lload                  # already open (e.g. an older kernel_patches.bin install)
    li      4, 0
    lis     3, logUnexpected@ha
    addi    3, 3, logUnexpected@l
    bl      LogLine
    b       .Ldone

.Lpatch:
    lis     4, GATE_ORIGINAL_HI
    ori     4, 4, GATE_PATCHED_LO
    bl      SetGateWord
    li      11, 1
    stw     11, 0x94(1)

.Lload:
    li      4, 0
    lis     3, logPre@ha
    addi    3, 3, logPre@l
    bl      LogLine
    lis     3, pathHid@ha
    addi    3, 3, pathHid@l
    li      4, 8                    # system DLL
    li      5, 0
    addi    6, 1, 0x88
    bl      XexLoadImage
    stw     3, 0xA0(1)
    mr      4, 3
    lis     3, logLoad@ha
    addi    3, 3, logLoad@l
    bl      LogLine

    lwz     11, 0x94(1)
    cmpwi   11, 0
    beq     .Ldone
    lis     4, GATE_ORIGINAL_HI
    ori     4, 4, GATE_ORIGINAL_LO
    bl      SetGateWord
    lis     9, 0x8007
    ori     9, 9, 0x8FAC
    lwz     4, 0(9)
    lis     3, logRestored@ha
    addi    3, 3, logRestored@l
    bl      LogLine

.Ldone:
    li      3, 1
    addi    1, 1, 0x100
    lwz     12, -8(1)
    mtlr    12
    blr


# SetGateWord(r4 = instruction): writes the module-loader gate and makes it visible to
# instruction fetch on all cores.
SetGateWord:
    lis     9, 0x8007
    ori     9, 9, 0x8FAC
    stw     4, 0(9)
    dcbst   0, 9
    sync
    icbi    0, 9
    sync
    isync
    blr

# IsTrayOpen: SMC query 0x0A (same check hiddriver uses). Returns r3 = 1 if the tray is open.
IsTrayOpen:
    mflr    12
    stw     12, -8(1)
    stwu    1, -0x60(1)
    li      10, 0
    stw     10, 0x20(1)
    stw     10, 0x24(1)
    stw     10, 0x28(1)
    stw     10, 0x2C(1)
    stw     10, 0x30(1)
    stw     10, 0x34(1)
    stw     10, 0x38(1)
    stw     10, 0x3C(1)
    li      10, 0x0A
    stb     10, 0x20(1)
    addi    3, 1, 0x20
    addi    4, 1, 0x30
    bl      HalSendSMCMessage
    lbz     3, 0x31(1)
    xori    3, 3, 0x60
    cntlzw  3, 3
    srwi    3, 3, 5                 # r3 = (Output[1] == 0x60)
    addi    1, 1, 0x60
    lwz     12, -8(1)
    mtlr    12
    blr


# LogLine(r3 = ASCII text, r4 = value): appends "text XXXXXXXX\r\n" to loader.log. Each load
# recreates the file on its first line.
LogLine:
    mflr    12
    stw     12, -8(1)
    stwu    1, -0x100(1)
    lis     9, logBuf@ha
    addi    9, 9, logBuf@l
1:  lbz     10, 0(3)
    cmpwi   10, 0
    beq     2f
    stb     10, 0(9)
    addi    3, 3, 1
    addi    9, 9, 1
    b       1b
2:  li      10, ' '
    stb     10, 0(9)
    addi    9, 9, 1
    li      10, 8
    mtctr   10
3:  rlwinm  11, 4, 4, 28, 31
    rotlwi  4, 4, 4
    cmplwi  11, 10
    blt     4f
    addi    11, 11, 7
4:  addi    11, 11, '0'
    stb     11, 0(9)
    addi    9, 9, 1
    bdnz    3b
    li      10, 0x0D0A
    sth     10, 0(9)
    addi    9, 9, 2
    lis     10, logBuf@ha
    addi    10, 10, logBuf@l
    subf    9, 10, 9
    stw     9, 0x60(1)
    li      11, 0x60
    stw     11, 0x54(1)             # 9th arg: FILE_SYNCHRONOUS_IO_NONALERT | FILE_NON_DIRECTORY_FILE
    addi    3, 1, 0x70
    lis     4, 0x4010               # GENERIC_WRITE | SYNCHRONIZE
    lis     5, logAttr@ha
    addi    5, 5, logAttr@l
    addi    6, 1, 0x78
    li      7, 0
    li      8, 0x80
    li      9, 1
    lis     10, logDisposition@ha
    lwz     10, logDisposition@l(10)
    bl      NtCreateFile
    cmpwi   3, 0
    bne     5f
    lis     11, logDisposition@ha
    li      10, 3                   # FILE_OPEN_IF after the first line
    stw     10, logDisposition@l(11)
    lwz     3, 0x70(1)
    li      4, 0
    li      5, 0
    li      6, 0
    addi    7, 1, 0x78
    lis     8, logBuf@ha
    addi    8, 8, logBuf@l
    lwz     9, 0x60(1)
    lis     10, logOffset@ha
    addi    10, 10, logOffset@l
    bl      NtWriteFile
    lis     11, logOffset@ha
    addi    11, 11, logOffset@l
    lwz     10, 4(11)
    lwz     9, 0x60(1)
    add     10, 10, 9
    stw     10, 4(11)
    lwz     3, 0x70(1)
    bl      NtClose
5:  addi    1, 1, 0x100
    lwz     12, -8(1)
    mtlr    12
    blr

    .section .data,"aw"
    .p2align 3
logOffset:
    .long   0, 0
logDisposition:
    .long   5                           # FILE_OVERWRITE_IF for the first line
logAttr:
    .long   0, logNameStr, 0x40
logNameStr:
    .short  logPathEnd - logPath, logPathEnd - logPath + 1
    .long   logPath
strLink:
    .short  linkEnd - linkStr, linkEnd - linkStr
    .long   linkStr
strDevice:
    .short  devEnd - devStr, devEnd - devStr
    .long   devStr
logBuf:     .space 128
linkStr:    .ascii "\\??\\HDD:"
linkEnd:
devStr:     .ascii "\\Device\\Harddisk0\\Partition1"
devEnd:
    .byte 0
#ifdef CHAIN
logPath:    .ascii "\\Device\\Harddisk0\\Partition1\\PeerPressure\\SideLoading\\HidDriver\\aurora-loader.log"
#else
logPath:    .ascii "\\Device\\Harddisk0\\Partition1\\PeerPressure\\SideLoading\\HidDriver\\sideload-loader.log"
#endif
logPathEnd:
    .byte 0
nameHid:    .asciz "hiddriver.xex"
pathHid:    .asciz "\\Device\\Harddisk0\\Partition1\\PeerPressure\\SideLoading\\HidDriver\\hiddriver.xex"
#ifdef CHAIN
pathFixer:  .asciz "\\Device\\Harddisk0\\Partition1\\PeerPressure\\SideLoading\\AuroraFixer.orig.xex"
logEntry:       .asciz "== HidLoader v4 (AuroraFixer chain) entered, reason"
logFixer:       .asciz "XexLoadImage AuroraFixer.orig.xex (flag 9) returned"
#else
logEntry:       .asciz "== HidLoader v4 (sideload) entered, reason"
#endif
logLink:        .asciz "ObCreateSymbolicLink HDD: returned"
logLoaded:      .asciz "hiddriver already loaded, nothing to do"
logTray:        .asciz "disc tray open (1 = skip hiddriver)"
logGate:        .asciz "kernel gate @80078FAC ="
logUnexpected:  .asciz "unexpected kernel gate instruction - not loading (needs kernel 17559)"
logPre:         .asciz "loading hiddriver.xex (flag 8)"
logLoad:        .asciz "XexLoadImage hiddriver.xex returned"
logRestored:    .asciz "kernel gate restored ="
