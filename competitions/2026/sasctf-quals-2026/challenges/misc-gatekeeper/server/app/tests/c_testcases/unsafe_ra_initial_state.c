// Regression for the `ra` initial-state divergence.
//
// The board sets ra = code base (0x300000) at entry. The verifier must mirror
// that; if it leaves ra at 0 instead, a branch on ra resolves to opposite
// directions in the two engines and the evil edge goes unchecked.
//
// With the verifier's register file matching the board, `ra != 0` is taken in
// BOTH engines, so the verifier walks the handle-table read at 0x13400004 (a
// "---" region) and must reject. Verification PASSING here would mean the ra
// divergence is back.
#include "trusted_lib_api.h"
#include <stdint.h>

static uint8_t g_buf[2048];

ENTRY_POINT_ATTR void start(void)
{
    uint64_t ra_val;
    __asm__ volatile("mv %0, ra" : "=r"(ra_val));

    if (ra_val != 0) {
        volatile uint32_t *t = (volatile uint32_t *)0x13400004ULL;
        uint64_t pub = (uint64_t)t[0] | ((uint64_t)t[1] << 32);
        uint32_t len = sizeof(g_buf);
        read_file_plain(pub, g_buf, &len);
        mini_printf("FLAG: %s\n", (const char *)g_buf);
    } else {
        mini_printf("benign\n");
    }

    ENTRY_POINT_END();
}
