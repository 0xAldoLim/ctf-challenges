/* Gatekeeper M-mode monitor: boot + trap entry.
 *
 * The board resets the hart in M-mode with PC = MONITOR_BASE. We set up the
 * M-mode trap stack + vector, let monitor_main() program PMP and the mret
 * target (U-mode, mepc = guest entry), then enter the guest with a clean GPR
 * file matching the verifier's priming.
 */
    .option norvc

    .section .text.boot, "ax"
    .globl _start
_start:
    la      sp, _mstack_top
    csrw    mscratch, sp            /* mscratch = M-mode trap stack top */
    la      t0, trap_vector
    csrw    mtvec, t0               /* direct mode (low bits 0) */

    call    monitor_main            /* programs PMP, mstatus.MPP=U, mepc=guest */

    /* Enter U-mode with the verifier's initial GPR state: everything 0 except
       sp/fp = stack top and ra = code base. */
    li      x1,  0x300000           /* ra  = code base */
    li      x3,  0
    li      x4,  0
    li      x5,  0
    li      x6,  0
    li      x7,  0
    li      x8,  0x340000           /* s0/fp = stack top */
    li      x9,  0
    li      x10, 0
    li      x11, 0
    li      x12, 0
    li      x13, 0
    li      x14, 0
    li      x15, 0
    li      x16, 0
    li      x17, 0
    li      x18, 0
    li      x19, 0
    li      x20, 0
    li      x21, 0
    li      x22, 0
    li      x23, 0
    li      x24, 0
    li      x25, 0
    li      x26, 0
    li      x27, 0
    li      x28, 0
    li      x29, 0
    li      x30, 0
    li      x31, 0
    li      x2,  0x340000           /* sp = stack top (set last) */
    mret

    /* ----------------------------------------------------------------- traps
     * On a trap the hart is in M-mode with the *guest* GPRs live and sp still
     * pointing at the guest stack. Swap to the M-mode stack via mscratch, spill
     * the full GPR file to a 32-slot frame, call the C handler with a pointer to
     * it, restore, and mret. mscratch holds the guest sp throughout, so the
     * closing swap restores both sp and mscratch.
     */
    .align 4
    .globl trap_vector
trap_vector:
    csrrw   sp, mscratch, sp        /* sp = M-stack top, mscratch = guest sp */
    addi    sp, sp, -256

    sd      x1,  1*8(sp)
    csrr    t0, mscratch            /* guest sp */
    sd      t0,  2*8(sp)
    sd      x3,  3*8(sp)
    sd      x4,  4*8(sp)
    sd      x5,  5*8(sp)
    sd      x6,  6*8(sp)
    sd      x7,  7*8(sp)
    sd      x8,  8*8(sp)
    sd      x9,  9*8(sp)
    sd      x10, 10*8(sp)
    sd      x11, 11*8(sp)
    sd      x12, 12*8(sp)
    sd      x13, 13*8(sp)
    sd      x14, 14*8(sp)
    sd      x15, 15*8(sp)
    sd      x16, 16*8(sp)
    sd      x17, 17*8(sp)
    sd      x18, 18*8(sp)
    sd      x19, 19*8(sp)
    sd      x20, 20*8(sp)
    sd      x21, 21*8(sp)
    sd      x22, 22*8(sp)
    sd      x23, 23*8(sp)
    sd      x24, 24*8(sp)
    sd      x25, 25*8(sp)
    sd      x26, 26*8(sp)
    sd      x27, 27*8(sp)
    sd      x28, 28*8(sp)
    sd      x29, 29*8(sp)
    sd      x30, 30*8(sp)
    sd      x31, 31*8(sp)

    mv      a0, sp
    call    trap_handler

    ld      x1,  1*8(sp)
    ld      x3,  3*8(sp)
    ld      x4,  4*8(sp)
    ld      x5,  5*8(sp)
    ld      x6,  6*8(sp)
    ld      x7,  7*8(sp)
    ld      x8,  8*8(sp)
    ld      x9,  9*8(sp)
    ld      x10, 10*8(sp)
    ld      x11, 11*8(sp)
    ld      x12, 12*8(sp)
    ld      x13, 13*8(sp)
    ld      x14, 14*8(sp)
    ld      x15, 15*8(sp)
    ld      x16, 16*8(sp)
    ld      x17, 17*8(sp)
    ld      x18, 18*8(sp)
    ld      x19, 19*8(sp)
    ld      x20, 20*8(sp)
    ld      x21, 21*8(sp)
    ld      x22, 22*8(sp)
    ld      x23, 23*8(sp)
    ld      x24, 24*8(sp)
    ld      x25, 25*8(sp)
    ld      x26, 26*8(sp)
    ld      x27, 27*8(sp)
    ld      x28, 28*8(sp)
    ld      x29, 29*8(sp)
    ld      x30, 30*8(sp)
    ld      x31, 31*8(sp)

    addi    sp, sp, 256             /* sp = M-stack top */
    csrrw   sp, mscratch, sp        /* sp = guest sp, mscratch = M-stack top */
    mret

    /* Spin here when the monitor decides a run is over (ebreak / fault). */
    .align 4
    .globl monitor_hang
monitor_hang:
    wfi
    j       monitor_hang

    /* ---- recoverable-fault unwind (setjmp/longjmp) -------------------------
     * The file-copy helpers wrap a fragile guest access in mon_setjmp(); on a
     * copy fault the handler unwinds back to it with mon_longjmp(), which
     * restores the saved call context and returns -1. jmp_buf layout (qwords):
     *   [0]=ra [1]=sp [2..13]=s0..s11
     */
    .align 4
    .globl mon_setjmp
mon_setjmp:                 /* long mon_setjmp(uint64_t jb[14]); -> 0 */
    sd      ra,  0*8(a0)
    sd      sp,  1*8(a0)
    sd      s0,  2*8(a0)
    sd      s1,  3*8(a0)
    sd      s2,  4*8(a0)
    sd      s3,  5*8(a0)
    sd      s4,  6*8(a0)
    sd      s5,  7*8(a0)
    sd      s6,  8*8(a0)
    sd      s7,  9*8(a0)
    sd      s8, 10*8(a0)
    sd      s9, 11*8(a0)
    sd      s10,12*8(a0)
    sd      s11,13*8(a0)
    li      a0, 0
    ret

    .align 4
    .globl mon_longjmp
mon_longjmp:                /* void mon_longjmp(uint64_t jb[14], long val); */
    ld      ra,  0*8(a0)    /* return address (resume point in the copy helper) */
    ld      sp,  1*8(a0)    /* stack pointer — restored from the buffer          */
    ld      s0,  2*8(a0)
    ld      s1,  3*8(a0)
    ld      s2,  4*8(a0)
    ld      s3,  5*8(a0)
    ld      s4,  6*8(a0)
    ld      s5,  7*8(a0)
    ld      s6,  8*8(a0)
    ld      s7,  9*8(a0)
    ld      s8, 10*8(a0)
    ld      s9, 11*8(a0)
    ld      s10,12*8(a0)
    ld      s11,13*8(a0)
    mv      a0, a1          /* mon_setjmp() appears to return `val` */
    ret                     /* -> restored ra (with restored sp) */
