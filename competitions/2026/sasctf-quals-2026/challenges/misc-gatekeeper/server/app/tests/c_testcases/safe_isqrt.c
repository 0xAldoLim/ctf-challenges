#include "trusted_lib_api.h"

// isqrt with a concrete argument -> exact result, safe to verify.
ENTRY_POINT_ATTR void start()
{
    uint64_t r = TRUSTED_CALL(isqrt, 1000000ULL); // = 1000
    TRUSTED_CALL_VOID(mini_printf, "isqrt(1000000) = %llx\n", r);
    ENTRY_POINT_END();
}
