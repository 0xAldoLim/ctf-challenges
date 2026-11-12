#include "trusted_lib_api.h"
#include <stdint.h>

// Positive control for the frame-alias guard. Buffers in the data segment sit
// far BELOW sp but nowhere near the callee frame window [sp-512, sp). The guard
// keys on that window, not on "addr < sp", so passing data-segment buffers to
// the file APIs must still verify (no over-rejection).
static uint8_t databuf[64];
static uint32_t datalen;

ENTRY_POINT_ATTR void start()
{
    uint64_t h = TRUSTED_CALL(create_file_plain, databuf, 16);
    datalen = sizeof(databuf);
    TRUSTED_CALL(read_file_plain, h, databuf, &datalen);
    ENTRY_POINT_END();
}
