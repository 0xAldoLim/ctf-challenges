/* 3-operand jalr operand-confusion attempt: `jalr a5, a4, 0` with a5 (=rd, a
 * proven-single &safe) and a4 (=rs1, the real target) = &evil. A verifier that
 * pinned the first register operand (rd) would walk safe() and accept; the fixed
 * resolver pins rs1 (a4) and follows the *real* target into evil(), whose raw
 * ecall is rejected. Must FAIL. */
#include "trusted_lib_api.h"
#include <stdint.h>

__attribute__((noinline)) static void evil(void) { __asm__ volatile("ecall"); for (;;) {} }
__attribute__((noinline)) static void safe_path(void) { __asm__ volatile("ebreak"); for (;;) {} }

ENTRY_POINT_ATTR void start(void)
{
    static uint8_t inp[8];
    uint32_t len = sizeof(inp);
    read_file_plain(0, inp, &len); /* make inp[0] symbolic so the proof engages */
    uint32_t s = (uint32_t)(uintptr_t)&safe_path;
    uint64_t a5 = verifier_ranged_u32((uint32_t)inp[0], s, s);
    uint64_t a4 = (uint64_t)(uintptr_t)&evil;
    __asm__ volatile(
        "mv a5, %[s]\n"
        "mv a4, %[e]\n"
        "jalr a5, a4, 0\n"
        :
        : [s] "r"(a5), [e] "r"(a4)
        : "a4", "a5", "ra", "memory");
    halt();
}
