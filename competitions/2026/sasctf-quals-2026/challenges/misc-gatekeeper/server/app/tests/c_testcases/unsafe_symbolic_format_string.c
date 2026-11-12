#include "trusted_lib_api.h"
#include <stdint.h>

// A file-backed buffer is symbolic to the verifier: its concrete value is 0, so
// reading it as a format string yields an EMPTY format with no conversions to
// validate. At runtime that same buffer holds attacker bytes ("%s"), so the real
// mini_printf parses a %s and dereferences a pointer the verifier never checked
// (here the forbidden handle table at 0x13400004). The format string must be
// concrete, so this program must be rejected.
ENTRY_POINT_ATTR void start()
{
    static uint8_t pctS[8];
    pctS[0] = '%';
    pctS[1] = 's';
    pctS[2] = 0;
    uint64_t hf = TRUSTED_CALL(create_file_plain, pctS, 4);

    static uint8_t fmt[16];
    static uint32_t l1;
    l1 = 16;
    TRUSTED_CALL(read_file_plain, hf, fmt, &l1); // fmt: symbolic, "%s" at runtime

    TRUSTED_CALL_VOID(mini_printf, (const char *)fmt, (uint64_t)0x13400004);
    ENTRY_POINT_END();
}
