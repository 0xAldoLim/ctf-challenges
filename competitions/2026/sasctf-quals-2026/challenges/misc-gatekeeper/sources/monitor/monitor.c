/* Gatekeeper M-mode monitor.
 *
 * Confines the guest to U-mode under PMP, then services the guest syscall ABI
 * (ecall) and ends the run on a fault. The privileged file/handle logic lives
 * here (M-mode). Guest buffers are touched the idiomatic way: with
 * `mstatus.MPRV=1, MPP=U` so the hardware applies U-mode PMP to the monitor's
 * own loads/stores -- a stray guest pointer faults instead of letting M-mode
 * read protected memory on the guest's behalf. A fault while *reading* guest
 * input is recoverable (return -1, like copy_from_user); a fault while *writing*
 * the guest's output is fatal.
 */

#include <stdint.h>

/* ---- machine constants (mirror the board / device / verifier) ---- */
#define UART0_BASE 0x10000000UL
#define UART_THR 0x00
#define UART_RHR 0x00
#define UART_LSR 0x05
#define UART_LSR_DR 0x01

#define GUEST_ENTRY 0x00300000UL

#define USER_CODE_BASE 0x00300000UL
#define USER_CODE_SIZE 0x00010000UL
#define USER_DATA_BASE 0x00310000UL
#define USER_DATA_SIZE 0x00010000UL
#define USER_STACK_BASE 0x00320000UL
#define USER_STACK_SIZE 0x00020000UL

/* gatekeeper file device (MMIO) + handle table — M-mode only */
#define MMIO_BASE 0x13370000UL
#define HANDLES_BASE 0x13400000UL
#define MAX_FILE_SIZE (2048 + 12)

#define REG_MODE 0x00
#define REG_STATUS 0x04
#define REG_LENDW 0x08
#define REG_FILEDW 0x0C
#define REG_PUB_HANDLE_LO 0x10
#define REG_PUB_HANDLE_HI 0x14
#define REG_PRIV_HANDLE_LO 0x18
#define REG_PRIV_HANDLE_HI 0x1C

#define MODE_CREATE_PLAIN 0x1100
#define MODE_READ_PLAIN 0x1200
#define GATEKEEPER_EOK 0
#define GATEKEEPER_ENOSPACE 1

typedef struct __attribute__((packed)) {
    uint64_t public_handle;
    uint64_t private_handle;
    uint32_t encrypted;
} HandleEntry;

typedef struct {
    uint32_t total_entries;
    HandleEntry entries[];
} HandleTable;

#define HANDLES_MAX_ENTRIES ((0x80000UL - sizeof(uint32_t)) / sizeof(HandleEntry))

static volatile HandleTable *const g_table = (volatile HandleTable *)HANDLES_BASE;

/* syscall numbers (a7) — keep in sync with the wrappers and the verifier */
enum {
    SYS_PUTC = 0,
    SYS_GETC = 1,
    SYS_FILE_CREATE = 2,
    SYS_FILE_READ = 3,
};

#define CAUSE_LOAD_MISALIGN 4
#define CAUSE_LOAD_ACCESS 5
#define CAUSE_STORE_MISALIGN 6
#define CAUSE_STORE_ACCESS 7
#define CAUSE_ECALL_U 8

/* PMP cfg bits */
#define PMP_R 0x01
#define PMP_W 0x02
#define PMP_X 0x04
#define PMP_A_NAPOT 0x18
#define PMP_L 0x80

/* Smepmp: Machine Mode Lockdown. Under MML, M-mode can only execute a region
   covered by an M-executable rule; U/unmatched code is non-executable in M.
   The cfg bytes below use the Smepmp encoding (op = L*8 + R*4 + W*2 + X):
     op13 (L|R|X)  = M:r-x  U:none   -> the monitor's own .text
     op5  (R|X)    = M:none U:r-x    -> user code / trusted-lib (U executes)
     op6  (R|W)    = M:none U:rw     -> user data / stack
   Everything unmatched (device, handle table, UART, monitor data+stack) is
   M-rw-but-not-executable by the MML default, so it needs no rule. */
#define MSECCFG_MML 0x1UL
#define MONITOR_TEXT_BASE 0x80010000UL
#define MONITOR_TEXT_SIZE 0x2000UL
#define TRUSTED_LIB_BASE 0x80000000UL
#define TRUSTED_LIB_SIZE 0x10000UL

#define MSTATUS_MPP (3UL << 11)
#define MSTATUS_MPRV (1UL << 17)

extern void monitor_hang(void) __attribute__((noreturn));

/* ---- low-level MMIO (M-mode direct) ---- */
static inline uint8_t mmio_rb(uint64_t addr) { return *(volatile uint8_t *)addr; }
static inline void mmio_wb(uint64_t addr, uint8_t v) { *(volatile uint8_t *)addr = v; }
static inline uint32_t dev_rd(uint32_t off) { return *(volatile uint32_t *)(MMIO_BASE + off); }
static inline void dev_wr(uint32_t off, uint32_t v) { *(volatile uint32_t *)(MMIO_BASE + off) = v; }

static uint64_t dev_rd_qw(uint32_t lo, uint32_t hi)
{
    return (uint64_t)dev_rd(lo) | ((uint64_t)dev_rd(hi) << 32);
}
static void dev_wr_qw(uint32_t lo, uint32_t hi, uint64_t v)
{
    dev_wr(lo, (uint32_t)v);
    dev_wr(hi, (uint32_t)(v >> 32));
}

static void uart_putc(char c) { mmio_wb(UART0_BASE + UART_THR, (uint8_t)c); }

static int32_t uart_getc(void)
{
    uint8_t lsr = mmio_rb(UART0_BASE + UART_LSR);
    if (!(lsr & UART_LSR_DR)) {
        return -1;
    }
    return (int32_t)mmio_rb(UART0_BASE + UART_RHR);
}

static void uart_puts(const char *s)
{
    while (*s) {
        uart_putc(*s++);
    }
}

/* ---- CSR helpers ---- */
#define CSR_READ(csr)                                                                              \
    ({                                                                                             \
        uint64_t __v;                                                                              \
        __asm__ volatile("csrr %0, " #csr : "=r"(__v));                                            \
        __v;                                                                                       \
    })
#define CSR_WRITE(csr, val) __asm__ volatile("csrw " #csr ", %0" ::"r"((uint64_t)(val)))

/* ---- recoverable guest-memory access (MPRV + setjmp/longjmp) ----
 * The monitor reaches guest memory with MPRV=1, MPP=U so loads/stores are
 * PMP-checked as U-mode: a bad guest pointer faults rather than letting M-mode
 * touch protected memory. Each copy helper wraps its guest access in
 * mon_setjmp(); on a copy fault, trap_handler resumes at copy_fault_resume(),
 * which mon_longjmp()s back to the helper (returning -1). trap_handler keys the
 * unwind on "MPRV was set at trap time", so it can only fire for an in-progress
 * guest copy.
 */
extern long mon_setjmp(uint64_t *jb);                                   /* start.S */
extern void mon_longjmp(uint64_t *jb, long val) __attribute__((noreturn));
static uint64_t g_copy_jb[14]; /* [0]=ra [1]=sp [2..13]=s0..s11 */

/* MUST stay inlined: these run *inside* the MPRV=U window, so any function
 * prologue/epilogue stack access would itself be U-checked against the M-stack
 * and fault. always_inline keeps them inline even under -fno-inline. */
static inline __attribute__((always_inline)) void mprv_user_set(void)
{
    uint64_t ms = CSR_READ(mstatus);
    ms &= ~MSTATUS_MPP; /* MPP = U */
    ms |= MSTATUS_MPRV;
    CSR_WRITE(mstatus, ms);
}
static inline __attribute__((always_inline)) void mprv_clear(void)
{
    CSR_WRITE(mstatus, CSR_READ(mstatus) & ~MSTATUS_MPRV);
}

/* Resume point after a copy fault (reached via mepc); unwinds to the helper. */
void __attribute__((noreturn, used, noinline)) copy_fault_resume(void)
{
    mon_longjmp(g_copy_jb, 1);
}

/* Read n bytes (n%4==0) from guest `uaddr` into M-local `dst`. 0 ok, -1 on a
 * bad guest pointer. */
static int __attribute__((noinline)) copy_from_user(uint32_t *dst, uint64_t uaddr, uint32_t n)
{
    if (mon_setjmp(g_copy_jb) != 0) { /* longjmp lands here on a copy fault */
        mprv_clear();
        return -1;
    }
    for (uint32_t i = 0; i < n / 4; i++) {
        /* MPRV brackets ONLY the guest read; the M-local store must run M-direct
           (under MPRV it would be U-checked and fault). */
        mprv_user_set();
        uint32_t v = *(volatile uint32_t *)(uaddr + i * 4); /* faults if uaddr is non-U */
        mprv_clear();
        dst[i] = v;
    }
    return 0;
}

/* Write n bytes (n%4==0) from M-local `src` to guest `uaddr`. Recoverable like
 * copy_from_user: a bad output pointer faults and returns -1. */
static int __attribute__((noinline)) copy_to_user(uint64_t uaddr, const uint32_t *src, uint32_t n)
{
    if (mon_setjmp(g_copy_jb) != 0) {
        mprv_clear();
        return -1;
    }
    for (uint32_t i = 0; i < n / 4; i++) {
        uint32_t v = src[i]; /* M-local read, M-direct */
        mprv_user_set();
        *(volatile uint32_t *)(uaddr + i * 4) = v; /* guest write; faults if non-U */
        mprv_clear();
    }
    return 0;
}

/* ---- handle table scan (constant-time, M-mode) ---- */
static int get_private_handle(uint64_t public_handle, uint64_t *private_handle, uint32_t *encrypted)
{
    uint64_t found = 0, found_private = 0, found_encrypted = 0;
    for (uint32_t i = 0; i < HANDLES_MAX_ENTRIES; ++i) {
        uint64_t ph = g_table->entries[i].public_handle;
        uint64_t mask = 0 - (uint64_t)((ph ^ public_handle) == 0);
        found_private |= g_table->entries[i].private_handle & mask;
        found_encrypted |= (uint64_t)g_table->entries[i].encrypted & mask;
        found |= (g_table->entries[i].private_handle != 0) ? mask : 0;
    }
    if (!found) {
        return -1;
    }
    *private_handle = found_private;
    *encrypted = (uint32_t)found_encrypted;
    return 0;
}

/* ---- file syscalls ----
 * Guest bytes are staged through an M-local bounce buffer so the MPRV window
 * brackets *only* the guest touch; the device MMIO is driven with MPRV off.
 */
static uint32_t g_bounce[MAX_FILE_SIZE / 4];

static uint64_t sys_file_create(uint64_t buf, uint32_t len)
{
    if (len == 0 || (len % 4) != 0) {
        return (uint64_t)-1;
    }
    if (len > MAX_FILE_SIZE) {
        len = MAX_FILE_SIZE;
    }
    /* read-from-guest: recoverable. A bad `buf` faults here and returns -1. */
    if (copy_from_user(g_bounce, buf, len) != 0) {
        return (uint64_t)-1;
    }

    dev_wr(REG_MODE, MODE_CREATE_PLAIN);
    if (dev_rd(REG_STATUS) == GATEKEEPER_ENOSPACE) {
        return (uint64_t)-1;
    }
    dev_wr(REG_LENDW, len / 4);
    for (uint32_t i = 0; i < len / 4; ++i) {
        dev_wr(REG_FILEDW, g_bounce[i]);
    }
    uint64_t pub = dev_rd_qw(REG_PUB_HANDLE_LO, REG_PUB_HANDLE_HI);
    (void)dev_rd_qw(REG_PRIV_HANDLE_LO, REG_PRIV_HANDLE_HI);
    return (dev_rd(REG_STATUS) == GATEKEEPER_EOK) ? pub : 0;
}

static int32_t sys_file_read(uint64_t public_handle, uint64_t buf, uint64_t len_ptr)
{
    /* read-from-guest: recoverable. A bad `len_ptr` faults here and returns -1. */
    uint32_t want;
    if (copy_from_user(&want, len_ptr, 4) != 0) {
        return -1;
    }
    if (want == 0 || (want % 4) != 0 || want > MAX_FILE_SIZE) {
        return -1;
    }

    uint64_t priv = 0;
    uint32_t enc = 0;
    if (get_private_handle(public_handle, &priv, &enc) != 0 || enc) {
        return -1;
    }

    dev_wr_qw(REG_PRIV_HANDLE_LO, REG_PRIV_HANDLE_HI, priv);
    dev_wr(REG_MODE, MODE_READ_PLAIN);
    uint32_t have = dev_rd(REG_LENDW) * 4;
    if (have > want) {
        return -1;
    }
    for (uint32_t i = 0; i < have / 4; ++i) {
        g_bounce[i] = dev_rd(REG_FILEDW);
    }

    /* write-to-guest: a fault delivering output is fatal. */
    uint32_t hv = have;
    copy_to_user(len_ptr, &hv, 4);
    if (have) {
        copy_to_user(buf, g_bounce, have);
    }
    return (dev_rd(REG_STATUS) == GATEKEEPER_EOK) ? 0 : -1;
}

/* ---- PMP: grant U-mode access only to the guest's own regions ---- */
static inline uint64_t napot(uint64_t base, uint64_t size)
{
    return (base >> 2) | ((size >> 3) - 1);
}

static void setup_pmp(void)
{
    CSR_WRITE(pmpaddr0, napot(MONITOR_TEXT_BASE, MONITOR_TEXT_SIZE)); /* monitor .text */
    CSR_WRITE(pmpaddr1, napot(USER_CODE_BASE, USER_CODE_SIZE));       /* user code */
    CSR_WRITE(pmpaddr2, napot(USER_DATA_BASE, USER_DATA_SIZE));       /* user data */
    CSR_WRITE(pmpaddr3, napot(USER_STACK_BASE, USER_STACK_SIZE));     /* user stack */
    CSR_WRITE(pmpaddr4, napot(TRUSTED_LIB_BASE, TRUSTED_LIB_SIZE));   /* trusted-lib */

    uint64_t cfg0 = PMP_A_NAPOT | PMP_L | PMP_R | PMP_X; /* op13: M r-x  (monitor text) */
    uint64_t cfg1 = PMP_A_NAPOT | PMP_R | PMP_X;         /* op5:  U r-x  (user code)    */
    uint64_t cfg2 = PMP_A_NAPOT | PMP_R | PMP_W;         /* op6:  U rw-  (user data)    */
    uint64_t cfg3 = PMP_A_NAPOT | PMP_R | PMP_W;         /* op6:  U rw-  (user stack)   */
    uint64_t cfg4 = PMP_A_NAPOT | PMP_R | PMP_X;         /* op5:  U r-x  (trusted-lib)  */
    CSR_WRITE(pmpcfg0,
              (cfg4 << 32) | (cfg3 << 24) | (cfg2 << 16) | (cfg1 << 8) | cfg0);

    /* Lock it down: from here M-mode can execute ONLY the .text window above;
       a hijacked control flow into U/unmatched memory faults instead of running
       guest gadgets in M-mode. (Sticky; the cfg bytes take their Smepmp meaning
       only after this write.) */
    __asm__ volatile("csrs 0x747, %0" ::"r"(MSECCFG_MML)); /* 0x747 = mseccfg */
}

/* ---- boot: arm PMP, target U-mode at the guest entry; start.S does the mret ---- */
void monitor_main(void)
{
    setup_pmp();

    uint64_t ms = CSR_READ(mstatus);
    ms &= ~MSTATUS_MPP;  /* MPP = 00 → return to U-mode */
    ms &= ~MSTATUS_MPRV; /* MPRV off */
    CSR_WRITE(mstatus, ms);

    CSR_WRITE(mepc, GUEST_ENTRY);
}

/* ---- syscall dispatch + trap handling ---- */
static void terminate(const char *why)
{
    uart_puts(why);
    /* ebreak exits QEMU promptly (helper_ebreak), so a faulting run ends fast. */
    __asm__ volatile("ebreak");
    monitor_hang(); /* unreachable */
}

/* regs[i] == guest xi at trap time; a0=x10 … a7=x17 */
void trap_handler(uint64_t *regs)
{
    /* Was the monitor mid guest-copy (MPRV set) when the trap fired? Sample it
       before clearing, then clear so the handler's own accesses are M-direct. */
    int was_copy = (CSR_READ(mstatus) & MSTATUS_MPRV) != 0;
    __asm__ volatile("csrc mstatus, %0" ::"r"(MSTATUS_MPRV));

    uint64_t cause = CSR_READ(mcause);

    if (cause == CAUSE_ECALL_U) {
        switch (regs[17]) { /* a7 = syscall number */
        case SYS_PUTC:
            uart_putc((char)regs[10]);
            regs[10] = 0;
            break;
        case SYS_GETC:
            regs[10] = (uint64_t)(int64_t)uart_getc();
            break;
        case SYS_FILE_CREATE:
            regs[10] = sys_file_create(regs[10], (uint32_t)regs[11]);
            break;
        case SYS_FILE_READ:
            regs[10] = (uint64_t)(int64_t)sys_file_read(regs[10], regs[11], regs[12]);
            break;
        default:
            regs[10] = (uint64_t)-1;
            break;
        }
        CSR_WRITE(mepc, CSR_READ(mepc) + 4); /* resume past the ecall */
        return;
    }

    /* Recoverable copy fault: a guest copy hit a bad pointer. Resume at
       copy_fault_resume(), which mon_longjmp()s back into the helper. Gated on
       `was_copy` (MPRV was set), which is true only for an in-progress copy. The
       trampoline mret restores MPP correctly before we land at the resume. */
    if (was_copy &&
        (cause == CAUSE_LOAD_ACCESS || cause == CAUSE_STORE_ACCESS ||
         cause == CAUSE_LOAD_MISALIGN || cause == CAUSE_STORE_MISALIGN)) {
        CSR_WRITE(mepc, (uint64_t)&copy_fault_resume);
        return;
    }

    terminate("\n[monitor] guest fault\n"); /* PMP violation / illegal insn / ebreak-from-M / … */
}
