#include "trusted_lib_api.h"
#include <stdint.h>

// A trusted routine builds a stack frame below the caller's sp at runtime and
// leaves residue there (saved regs / canary / scrub-trampoline address). The
// engine does not model that frame, so it re-taints the scratch region below sp
// after every trusted call. Storing a value below sp, calling a trusted routine,
// then reading that slot back must therefore be rejected: the runtime would not
// have preserved the stored value, so the load reads undefined memory. A model
// that left the slot defined would let the guest branch on a value that differs
// between verifier and runtime (a control-flow desync).
ENTRY_POINT_ATTR void start()
{
    uint64_t v;
    __asm__ volatile(
        "sd   zero, -8(sp)\n"      // define [sp-8] = 0 in the verifier
        "li   t0, 0x80008000\n"    // readc entry point
        "jalr ra, 0(t0)\n"         // trusted call: clobbers [sp-frame, sp) at runtime
        "ld   %0, -8(sp)\n"        // read it back -> undefined after the call
        : "=r"(v)
        :
        : "t0", "ra", "memory");
    if (v)
        TRUSTED_CALL_VOID(mini_printf, "x\n");
    ENTRY_POINT_END();
}
