#include "trusted_lib_api.h"

// Branches on an untrusted symbolic input byte -> symbolic PC -> must be rejected.
__attribute__((noinline)) void unsafe_readc(void)
{
    int32_t c = TRUSTED_CALL(readc);
    if (c == 0x41) {
        TRUSTED_CALL_VOID(mini_printf, "A\n");
    } else {
        TRUSTED_CALL_VOID(mini_printf, "not A\n");
    }
}

ENTRY_POINT_ATTR void start()
{
    unsafe_readc();
    ENTRY_POINT_END();
}
