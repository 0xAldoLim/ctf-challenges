#include "trusted_lib_api.h"
#include <stdint.h>

// mini_printf's "%%" is a literal percent, not the start of a conversion. The
// format "%%x%s" therefore has exactly ONE conversion (%s), which the real
// routine binds to the first vararg (a1). Here a1 points at the forbidden
// handle table (0x13400004): a faithful shim binds %s to a1 and rejects the
// read. A shim that substring-counts the "%x" inside "%%x" would instead bind
// %s to a2 (benign) and accept -> verifier/runtime desync, arbitrary read.
static char benign[2] = {0, 0};

ENTRY_POINT_ATTR void start()
{
    volatile uint64_t target = 0x13400004ULL;
    TRUSTED_CALL_VOID(mini_printf, "%%x%s", (void *)(uintptr_t)target, (void *)benign);
    ENTRY_POINT_END();
}
