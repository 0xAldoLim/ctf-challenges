#include "trusted_lib_api.h"

__attribute__((noinline)) void safe_call_all_apis()
{
    uint8_t fbytes_plain[16] = { 0 };
    uint32_t len_plain = sizeof(fbytes_plain);

    uint64_t handle = TRUSTED_CALL(create_file_plain, fbytes_plain, sizeof(fbytes_plain));
    TRUSTED_CALL(read_file_plain, handle, fbytes_plain, &len_plain);

    TRUSTED_CALL_VOID(mini_printf, "called all apis\n");
}

ENTRY_POINT_ATTR void start()
{
    safe_call_all_apis();
    ENTRY_POINT_END();
}
