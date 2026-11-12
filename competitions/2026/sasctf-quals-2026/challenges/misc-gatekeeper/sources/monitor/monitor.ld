/* Gatekeeper M-mode monitor: raw binary loaded at MONITOR_BASE. */
ENTRY(_start)

MONITOR_BASE = 0x80010000;
MONITOR_TOP  = 0x80050000;   /* top of the trusted-funcs RAM window */

SECTIONS
{
    . = MONITOR_BASE;

    .text : {
        *(.text.boot)        /* _start must come first */
        *(.text*)
    }
    /* Code occupies the M-executable PMP window [0x80010000, 0x80012000) (op13:
       M=r-x). All writable/readable data lives above it and is M-rw via the MML
       "unmatched" default (and never M-executable). Keep .text < 0x2000. */
    . = MONITOR_BASE + 0x2000;
    .rodata : { *(.rodata*) }
    .data   : { *(.data*) }
    . = ALIGN(16);
    .bss : {
        __bss_start = .;
        *(.bss*)
        *(COMMON)
        __bss_end = .;
    }

    /* M-mode trap stack lives just below the top of the RAM window. */
    _mstack_top = MONITOR_TOP;
}
