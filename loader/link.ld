ENTRY(DllMain)
PHDRS { hdr PT_LOAD FILEHDR PHDRS; text PT_LOAD; data PT_LOAD; }
SECTIONS
{
    . = 0x89000000 + SIZEOF_HEADERS;
    . = 0x89010000;
    .text : { *(.text) *(.kthunks) } :text
    . = 0x89020000;
    .data : { *(.kvars) . = ALIGN(16); *(.data) } :data
    /DISCARD/ : { *(.comment) *(.note*) *(.eh_frame*) }
}
