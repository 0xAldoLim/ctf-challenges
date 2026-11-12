// fuzz_message.cpp — libFuzzer harness for the SMC1 decoder (message.cpp).
//
// Hunts UNINTENDED memory bugs in parse / pass-1 decode / pass-2 composite /
// teardown. The ONE intended bug (the stride overflow) is compiled out via
// -DSASMEDIA_FUZZ (guard in message.cpp) so it doesn't mask everything; without
// that define the harness instead crashes fast on the by-design primitive, which
// is a useful coverage check (it proves the fuzzer reaches the decode). See
// tools/fuzz.sh.
#include "../message.hpp"

#include <cstddef>
#include <cstdint>

extern "C" int LLVMFuzzerTestOneInput(const std::uint8_t* data, std::size_t size) {
    sasmedia::RenderedMessage out;            // RAII; freed at scope exit
    sasmedia::compose_message(data, size, out);
    return 0;
}
