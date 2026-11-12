#include "trusted_lib_api.h"

// The symbolic isqrt result may be used as data, but NOT for control flow:
// branching on it is symbolic PC and must be rejected.
ENTRY_POINT_ATTR void start()
{
    int32_t c = TRUSTED_CALL(readc);
    uint64_t r = TRUSTED_CALL(isqrt, (uint64_t)(uint32_t)c);
    if (r == 5) {
        TRUSTED_CALL_VOID(mini_printf, "five\n");
    } else {
        TRUSTED_CALL_VOID(mini_printf, "other\n");
    }
    ENTRY_POINT_END();
}
