#include "trusted_lib_api.h"
#include <stdint.h>

// create_file_plain reads its source bytes from a buffer that aliases its own
// frame (sp-8). At runtime the stub's prologue spills saved regs over that slice
// before the read, so the routine sends frame residue to the device rather than
// the bytes the verifier validated. Must be rejected.
ENTRY_POINT_ATTR void start()
{
    __asm__ volatile(
        "addi a0, sp, -8\n"     // fbytes (source) -> create_file_plain's own frame
        "li   a1, 8\n"          // len
        "li   t0, 0x80000000\n" // create_file_plain entry
        "jalr ra, 0(t0)\n"
        :
        :
        : "a0", "a1", "t0", "ra", "memory");
    ENTRY_POINT_END();
}
