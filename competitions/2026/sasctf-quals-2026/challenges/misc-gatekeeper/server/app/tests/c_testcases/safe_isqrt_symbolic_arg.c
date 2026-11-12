#include "trusted_lib_api.h"

// isqrt of a symbolic (input-derived) value: the loose model returns a fresh
// bounded symbolic result. Using it as DATA (printing) is safe and must verify.
ENTRY_POINT_ATTR void start()
{
    int32_t c = TRUSTED_CALL(readc);
    uint64_t r = TRUSTED_CALL(isqrt, (uint64_t)(uint32_t)c);
    TRUSTED_CALL_VOID(mini_printf, "isqrt(input) = %llx\n", r);
    ENTRY_POINT_END();
}
