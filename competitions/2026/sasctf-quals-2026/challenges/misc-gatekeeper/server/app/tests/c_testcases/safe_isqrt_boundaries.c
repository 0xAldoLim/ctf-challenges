#include "trusted_lib_api.h"
#include <stdint.h>

// isqrt at boundary concrete inputs: all must verify (the model computes the
// exact result; correctness at these edges is asserted in test_isqrt.py).
ENTRY_POINT_ATTR void start()
{
    TRUSTED_CALL_VOID(mini_printf, "%llx\n", isqrt(0ULL));                    // 0
    TRUSTED_CALL_VOID(mini_printf, "%llx\n", isqrt(1ULL));                    // 1
    TRUSTED_CALL_VOID(mini_printf, "%llx\n", isqrt(3ULL));                    // 1
    TRUSTED_CALL_VOID(mini_printf, "%llx\n", isqrt(4ULL));                    // 2
    TRUSTED_CALL_VOID(mini_printf, "%llx\n", isqrt(0xFFFFFFFFULL));           // 2^16-1
    TRUSTED_CALL_VOID(mini_printf, "%llx\n", isqrt(0x100000000ULL));          // 2^16
    TRUSTED_CALL_VOID(mini_printf, "%llx\n", isqrt(0xFFFFFFFE00000001ULL));   // (2^32-1)^2
    TRUSTED_CALL_VOID(mini_printf, "%llx\n", isqrt(0x8000000000000000ULL));   // 2^63
    TRUSTED_CALL_VOID(mini_printf, "%llx\n", isqrt(0xFFFFFFFFFFFFFFFFULL));   // 2^64-1 -> 2^32-1
    ENTRY_POINT_END();
}
