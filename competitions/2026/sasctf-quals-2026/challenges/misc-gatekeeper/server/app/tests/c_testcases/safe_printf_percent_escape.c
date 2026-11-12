#include "trusted_lib_api.h"
#include <stdint.h>

// Legitimate use of mini_printf's "%%" literal-percent escape alongside a real
// %s to a readable, defined string. The format has exactly one conversion (%s),
// bound to a1 = benign; the shim must walk past "%%" without consuming a vararg
// and accept this program.
static char benign[2] = {0, 0};

ENTRY_POINT_ATTR void start()
{
    TRUSTED_CALL_VOID(mini_printf, "100%% done: %s\n", (void *)benign);
    ENTRY_POINT_END();
}
