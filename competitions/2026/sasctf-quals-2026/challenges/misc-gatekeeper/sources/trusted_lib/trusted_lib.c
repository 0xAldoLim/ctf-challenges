/* U-mode trusted-lib wrappers (layered design).
 *
 * These live at the fixed trusted-call addresses (0x80000000, …) the verifier
 * shims and the guest jumps to. The privileged primitives (console I/O, file
 * device, handle table) now live in the M-mode monitor; each wrapper reaches it
 * via `ecall`. The scrub trampoline (TRUSTED_RETURN) is kept verbatim, so the
 * post-call register state still matches the verifier's _SCRUBBED set.
 *
 * isqrt / mini_printf / out_* are copied unchanged from trusted_lib.c — they
 * only depend on putc() and pure arithmetic.
 */

#include <stdarg.h>
#include <stdint.h>

#include "trusted_lib.h"

/* syscall numbers (a7) — keep in sync with the monitor and the verifier */
enum {
    SYS_PUTC = 0,
    SYS_GETC = 1,
    SYS_FILE_CREATE = 2,
    SYS_FILE_READ = 3,
};

static inline long do_ecall(long num, long a0_, long a1_, long a2_)
{
    register long a0 __asm__("a0") = a0_;
    register long a1 __asm__("a1") = a1_;
    register long a2 __asm__("a2") = a2_;
    register long a7 __asm__("a7") = num;
    __asm__ volatile("ecall" : "+r"(a0) : "r"(a1), "r"(a2), "r"(a7) : "memory");
    return a0;
}

/* ---- console (internal; not a trusted entry, so no scrub) ---- */
void putc(char c) { (void)do_ecall(SYS_PUTC, (unsigned char)c, 0, 0); }

/* ---- trusted entries ---- */
TRUSTED_API(.READC)
int32_t readc(void)
{
    TRUSTED_MAYBE_FORCE_NONLEAF();
    long r = do_ecall(SYS_GETC, 0, 0, 0);
    TRUSTED_RETURN((int32_t)r);
}

TRUSTED_API(.CREATE_FILE_PLAIN)
uint64_t create_file_plain(uint8_t* fbytes, uint32_t len)
{
    TRUSTED_MAYBE_FORCE_NONLEAF();
    long r = do_ecall(SYS_FILE_CREATE, (long)(uintptr_t)fbytes, (long)len, 0);
    TRUSTED_RETURN((uint64_t)r);
}

TRUSTED_API(.READ_FILE_PLAIN)
int32_t read_file_plain(uint64_t public_handle, uint8_t* fbytes, uint32_t* len)
{
    TRUSTED_MAYBE_FORCE_NONLEAF();
    long r = do_ecall(SYS_FILE_READ, (long)public_handle, (long)(uintptr_t)fbytes,
                      (long)(uintptr_t)len);
    TRUSTED_RETURN((int32_t)r);
}

TRUSTED_API(.ISQRT)
uint64_t isqrt(uint64_t n)
{
    TRUSTED_MAYBE_FORCE_NONLEAF();

    uint64_t x = 0;
    uint64_t b = (uint64_t)1 << 62;
    while (b > n) {
        b >>= 2;
    }
    while (b) {
        uint64_t t = x + b;
        x >>= 1;
        if (n >= t) {
            n -= t;
            x += b;
        }
        b >>= 2;
    }
    TRUSTED_RETURN(x);
}

/* ---- mini_printf + helpers (copied from trusted_lib.c; putc now ecalls) ---- */
void out_str(const char* s)
{
    if (!s) {
        const char* n = "(null)";
        while (*n)
            putc(*n++);
        return;
    }
    while (*s)
        putc(*s++);
}

void out_u64_base(uint64_t v, uint32_t base)
{
    char buf[72] = { 0 };
    const char* digits = "0123456789abcdef";
    int32_t i = 0;

    if (base < 2 || base > 16)
        return;
    if (v == 0) {
        putc('0');
        return;
    }
    while (v) {
        buf[i++] = digits[v % base];
        v /= base;
    }
    buf[i] = '\0';
    while (i--)
        putc(buf[i]);
}

void out_i64_dec(int64_t x)
{
    if (x < 0) {
        putc('-');
        out_u64_base((uint64_t)(-(x + 1)) + 1u, 10);
    } else {
        out_u64_base((uint64_t)x, 10);
    }
}

void out_hex_fixed(uint64_t v, uint32_t nibble_count)
{
    for (int32_t i = (int32_t)nibble_count - 1; i >= 0; --i) {
        uint32_t nib = (uint32_t)((v >> (i * 4)) & 0xF);
        char c = (char)(nib < 10 ? ('0' + nib) : ('a' + (nib - 10)));
        putc(c);
    }
}

TRUSTED_API(.MINI_PRINTF) void mini_printf(const char* fmt, ...)
{
    TRUSTED_MAYBE_FORCE_NONLEAF();

    va_list ap;
    va_start(ap, fmt);

    while (*fmt) {
        if (*fmt != '%') {
            putc(*fmt++);
            continue;
        }
        fmt++;
        if (*fmt == '%') {
            putc('%');
            fmt++;
            continue;
        }
        if (fmt[0] == 'l' && fmt[1] == 'l' && fmt[2] == 'x') {
            uint64_t v = va_arg(ap, uint64_t);
            out_u64_base((uint64_t)v, 16);
            fmt += 3;
            continue;
        }
        switch (*fmt) {
        case 'b': {
            uint64_t v = va_arg(ap, uint64_t);
            out_u64_base(v, 2);
            fmt++;
            break;
        }
        case 'x': {
            uint32_t v = va_arg(ap, uint32_t);
            out_u64_base((uint64_t)v, 16);
            fmt++;
            break;
        }
        case 'd': {
            int32_t v = va_arg(ap, int32_t);
            out_i64_dec((int64_t)v);
            fmt++;
            break;
        }
        case 'c': {
            int32_t v = va_arg(ap, int32_t);
            putc((char)v);
            fmt++;
            break;
        }
        case 's': {
            const char* s = va_arg(ap, const char*);
            out_str(s);
            fmt++;
            break;
        }
        case 'p': {
            void* p = va_arg(ap, void*);
            uintptr_t u = (uintptr_t)p;
            putc('0');
            putc('x');
            out_hex_fixed((uint64_t)u, (uint32_t)(sizeof(uintptr_t) * 2));
            fmt++;
            break;
        }
        default:
            putc('%');
            if (*fmt)
                putc(*fmt++);
            break;
        }
    }

    va_end(ap);
    TRUSTED_RETURN_VOID();
}
