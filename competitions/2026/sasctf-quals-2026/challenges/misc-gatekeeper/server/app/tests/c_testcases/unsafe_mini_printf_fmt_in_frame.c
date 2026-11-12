#include "trusted_lib_api.h"
#include <stdint.h>

// mini_printf's format-string pointer aliases its own frame (sp-8). At runtime
// the routine spills its frame there before parsing, so it parses different
// bytes than the verifier read -- the format-string desync that lets a benign
// (verified) format become an attacker-chosen one at runtime. Must be rejected.
ENTRY_POINT_ATTR void start()
{
    __asm__ volatile(
        "addi a0, sp, -8\n"     // fmt -> mini_printf's own frame
        "li   t0, 0x8000a000\n" // mini_printf entry
        "jalr ra, 0(t0)\n"
        :
        :
        : "a0", "t0", "ra", "memory");
    ENTRY_POINT_END();
}
