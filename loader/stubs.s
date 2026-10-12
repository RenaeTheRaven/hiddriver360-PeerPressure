# Generated import thunks -- do not edit.
    .section .kthunks,"ax"

    .globl XexLoadImage
XexLoadImage:
    .long 0x01000199, 0x02000199, 0x7D6903A6, 0x4E800420

    .globl XexGetModuleHandle
XexGetModuleHandle:
    .long 0x01000195, 0x02000195, 0x7D6903A6, 0x4E800420

    .globl ObCreateSymbolicLink
ObCreateSymbolicLink:
    .long 0x01000103, 0x02000103, 0x7D6903A6, 0x4E800420

    .globl NtCreateFile
NtCreateFile:
    .long 0x010000D2, 0x020000D2, 0x7D6903A6, 0x4E800420

    .globl NtWriteFile
NtWriteFile:
    .long 0x010000FF, 0x020000FF, 0x7D6903A6, 0x4E800420

    .globl NtClose
NtClose:
    .long 0x010000CF, 0x020000CF, 0x7D6903A6, 0x4E800420

    .globl HalSendSMCMessage
HalSendSMCMessage:
    .long 0x01000029, 0x02000029, 0x7D6903A6, 0x4E800420

    .section .kvars,"aw"

    .globl __imp_XexLoadImage
__imp_XexLoadImage:
    .long 0x00000199

    .globl __imp_XexGetModuleHandle
__imp_XexGetModuleHandle:
    .long 0x00000195

    .globl __imp_ObCreateSymbolicLink
__imp_ObCreateSymbolicLink:
    .long 0x00000103

    .globl __imp_NtCreateFile
__imp_NtCreateFile:
    .long 0x000000D2

    .globl __imp_NtWriteFile
__imp_NtWriteFile:
    .long 0x000000FF

    .globl __imp_NtClose
__imp_NtClose:
    .long 0x000000CF

    .globl __imp_HalSendSMCMessage
__imp_HalSendSMCMessage:
    .long 0x00000029
