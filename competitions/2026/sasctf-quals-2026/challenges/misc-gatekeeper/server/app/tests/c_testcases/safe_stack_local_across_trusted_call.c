#include "trusted_lib_api.h"
#include <stdint.h>

// A normal stack local lives in the frame ABOVE sp; it survives a trusted call
// and is read back fine. The post-call frame re-taint must only cover the
// scratch region BELOW sp, so ordinary stack usage across a trusted call must
// still verify (no over-rejection).
static volatile uint64_t sink;

ENTRY_POINT_ATTR void start()
{
    volatile uint64_t local = 0x41;        // on the stack, above sp
    TRUSTED_CALL_VOID(mini_printf, "hi\n"); // trusted call
    sink = local;                           // reload after the call -> still defined
    ENTRY_POINT_END();
}
