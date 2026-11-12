#include "trusted_lib_api.h"

// Reads untrusted input bytes and echoes them as decimals. The input value is
// never used for control flow, so this is safe and must verify.
__attribute__((noinline)) void safe_readc(void)
{
    int32_t a = TRUSTED_CALL(readc);
    int32_t b = TRUSTED_CALL(readc);
    TRUSTED_CALL_VOID(mini_printf, "%d %d\n", a, b);
}

ENTRY_POINT_ATTR void start()
{
    safe_readc();
    ENTRY_POINT_END();
}
