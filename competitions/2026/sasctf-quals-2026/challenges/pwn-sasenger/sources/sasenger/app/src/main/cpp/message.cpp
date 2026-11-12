// message.cpp — "SMC1" container decode (the 0-click surface).
//
// Pipeline:
//   parse    — walk the container, bounds-checked, into part descriptors
//   pass 1   — decode every image surface into the arena (allocate all headers
//              and buffers, then fill them), so a message's surfaces are ready
//              as a batch before compositing
//   pass 2   — composite the parts one-by-one into display-ready output
//
// Surfaces (`Bitmap` headers and their pixel buffers) are carved from one
// per-message `Arena` so they sit in a known, contiguous order: each image's
// header precedes its pixel buffer, and one image's buffer precedes the next
// image's header.
//
// SPDX-License-Identifier: Proprietary
#include "message.hpp"

#include <cstring>

#include "arena.hpp"
#include "bitmap.hpp"

namespace sasmedia {
namespace {

// ---- limits ----------------------------------------------------------------
constexpr std::uint16_t kMaxParts = 64;
constexpr std::uint32_t kMaxDim = 4096;                 // per-axis image bound
constexpr std::uint32_t kMaxSurfaceBytes = 8u << 20;    // 8 MiB per surface
constexpr std::uint32_t kMaxTextLen = 64u << 10;        // 64 KiB
constexpr std::uint16_t kMaxPalette = 256;
constexpr std::uint8_t  kBytesPerPixel = 4;             // ARGB_8888

// ---- bounded little-endian reader ------------------------------------------
class Reader {
public:
    Reader(const std::uint8_t* p, std::size_t n) noexcept : cur_{p}, end_{p + n} {}

    [[nodiscard]] bool u8(std::uint8_t& v) noexcept { return take(&v, 1); }

    [[nodiscard]] bool u16(std::uint16_t& v) noexcept {
        std::uint8_t b[2];
        if (!take(b, 2)) return false;
        v = static_cast<std::uint16_t>(b[0] | (b[1] << 8));
        return true;
    }

    [[nodiscard]] bool u32(std::uint32_t& v) noexcept {
        std::uint8_t b[4];
        if (!take(b, 4)) return false;
        v = static_cast<std::uint32_t>(b[0]) | (static_cast<std::uint32_t>(b[1]) << 8) |
            (static_cast<std::uint32_t>(b[2]) << 16) | (static_cast<std::uint32_t>(b[3]) << 24);
        return true;
    }

    // Borrow `n` bytes in place (no copy); advances past them.
    [[nodiscard]] bool borrow(std::size_t n, const std::uint8_t*& out) noexcept {
        if (avail() < n) return false;
        out = cur_;
        cur_ += n;
        return true;
    }

    [[nodiscard]] std::size_t avail() const noexcept {
        return static_cast<std::size_t>(end_ - cur_);
    }

private:
    [[nodiscard]] bool take(void* dst, std::size_t n) noexcept {
        if (avail() < n) return false;
        std::memcpy(dst, cur_, n);
        cur_ += n;
        return true;
    }

    const std::uint8_t* cur_;
    const std::uint8_t* end_;
};

// ---- parsed descriptors (refer into the input buffer; no surfaces yet) -----
struct ImageDesc {
    std::uint32_t width;
    std::uint32_t height;
    std::uint32_t rowBytes;       // source row stride
    const std::uint8_t* data;     // source pixels (borrowed from the input buffer)
    std::uint32_t dataLen;
};

struct StickerDesc {
    int sticker_id;
    std::vector<std::uint32_t> palette;
};

struct PartDesc {
    PartKind kind;
    std::string text;             // Text
    std::size_t image_index = 0;  // Image  -> index into the ImageDesc list
    StickerDesc sticker;          // Sticker
};

// ---- parse: container -> part descriptors (bounds-checked) ------------------
bool parse(Reader& r, std::vector<PartDesc>& parts, std::vector<ImageDesc>& images) {
    const std::uint8_t* magic = nullptr;
    if (!r.borrow(4, magic) || std::memcmp(magic, "SMC1", 4) != 0) return false;

    std::uint8_t version = 0, flags = 0;
    std::uint16_t partCount = 0;
    if (!r.u8(version) || !r.u8(flags) || !r.u16(partCount)) return false;
    if (version != 1 || flags != 0 || partCount == 0 || partCount > kMaxParts) return false;

    parts.reserve(partCount);
    for (std::uint16_t i = 0; i < partCount; ++i) {
        std::uint8_t kind = 0;
        if (!r.u8(kind)) return false;

        switch (static_cast<PartKind>(kind)) {
        case PartKind::Text:
        case PartKind::Reply: {
            std::uint32_t len = 0;
            const std::uint8_t* bytes = nullptr;
            if (!r.u32(len) || len > kMaxTextLen || !r.borrow(len, bytes)) return false;
            PartDesc p;
            p.kind = static_cast<PartKind>(kind);   // Text or Reply (both u32 len | utf8)
            p.text.assign(reinterpret_cast<const char*>(bytes), len);
            parts.push_back(std::move(p));
            break;
        }
        case PartKind::Image: {
            std::uint16_t w = 0, h = 0;
            std::uint32_t rowBytes = 0, dataLen = 0;
            const std::uint8_t* data = nullptr;
            if (!r.u16(w) || !r.u16(h) || !r.u32(rowBytes) || !r.u32(dataLen)) return false;
            if (!r.borrow(dataLen, data)) return false;
            if (w == 0 || h == 0 || w > kMaxDim || h > kMaxDim) return false;

            // The decoded surface is logically width*height ARGB pixels.
            const std::uint64_t surfaceBytes =
                static_cast<std::uint64_t>(w) * h * kBytesPerPixel;
            if (surfaceBytes > kMaxSurfaceBytes) return false;

            // Source must carry the rows we will read: `height` rows of `width`
            // visible pixels, with rows `rowBytes` apart in the source.
            const std::uint64_t visibleRow = static_cast<std::uint64_t>(w) * kBytesPerPixel;
            if (rowBytes < visibleRow) return false;  // stride can't be narrower than a row
            const std::uint64_t srcNeeded =
                static_cast<std::uint64_t>(h - 1) * rowBytes + visibleRow;
            if (srcNeeded > dataLen) return false;

            PartDesc p;
            p.kind = PartKind::Image;
            p.image_index = images.size();
            images.push_back(ImageDesc{w, h, rowBytes, data, dataLen});
            parts.push_back(std::move(p));
            break;
        }
        case PartKind::Sticker: {
            std::uint16_t id = 0, n = 0;
            if (!r.u16(id) || !r.u16(n) || n > kMaxPalette) return false;
            StickerDesc s;
            s.sticker_id = id;
            s.palette.reserve(n);
            for (std::uint16_t k = 0; k < n; ++k) {
                std::uint32_t rgba = 0;
                if (!r.u32(rgba)) return false;
                s.palette.push_back(rgba);
            }
            PartDesc p;
            p.kind = PartKind::Sticker;
            p.sticker = std::move(s);
            parts.push_back(std::move(p));
            break;
        }
        default:
            return false;  // unknown part kind
        }
    }
    return true;
}

// Arena footprint for all image surfaces, with headroom so a benign decode never
// runs the region dry.
std::size_t arena_size_for(const std::vector<ImageDesc>& images) {
    std::size_t total = 256;  // base headroom
    for (const ImageDesc& im : images) {
        total += sizeof(Bitmap) + alignof(Bitmap);
        total += static_cast<std::size_t>(im.width) * im.height * kBytesPerPixel +
                 alignof(std::max_align_t);
    }
    return total;
}

// ---- pass 1: decode every image surface into the arena ----------------------
// (a) Allocate each image's header then its pixel buffer, in display order, and
//     bind the buffer to the header. Header-before-buffer means one surface's
//     pixels are immediately followed by the next surface's header.
// (b) Fill each buffer from its source rows.
bool decode_surfaces(Arena& arena, const std::vector<ImageDesc>& images,
                     std::vector<Bitmap*>& surfaces) {
    struct Plan {
        Bitmap* bm;
        std::uint8_t* dst;
        std::uint32_t height;
        std::uint32_t rowBytes;
        std::uint32_t visibleRow;
        const std::uint8_t* src;
    };
    std::vector<Plan> plans;
    plans.reserve(images.size());

    for (const ImageDesc& im : images) {
        const std::size_t surfaceBytes =
            static_cast<std::size_t>(im.width) * im.height * kBytesPerPixel;
        void* header = arena.allocate(sizeof(Bitmap), alignof(Bitmap));
        auto* dst = static_cast<std::uint8_t*>(arena.allocate(surfaceBytes, kBytesPerPixel));
        if (header == nullptr || dst == nullptr) return false;

        Bitmap* bm = ::new (header) Bitmap(im.width, im.height,
                                          im.width * kBytesPerPixel, dst);
        plans.push_back(Plan{bm, dst, im.height, im.rowBytes,
                             im.width * kBytesPerPixel, im.data});
        surfaces.push_back(bm);
    }

    for (const Plan& pl : plans) {
#ifdef SASMEDIA_FUZZ
        // Fuzz-only (never defined in the shipped build): pitch the destination by
        // the visible row (tight) so the intended stride overflow is neutralized
        // and the fuzzer can explore the rest of the parser for UNINTENDED bugs.
        const std::uint32_t dstPitch = pl.visibleRow;
#else
        const std::uint32_t dstPitch = pl.rowBytes;
#endif
        // Lay each source row into the surface at the source row stride.
        for (std::uint32_t y = 0; y < pl.height; ++y) {
            std::memcpy(pl.dst + static_cast<std::size_t>(y) * dstPitch,
                        pl.src + static_cast<std::size_t>(y) * pl.rowBytes,
                        pl.visibleRow);
        }
    }
    return true;
}

// ---- pass 2: composite one image surface into a display preview -------------
// Walks the surface row-by-row (respecting its row pitch) into a fresh preview.
RenderedPart render_image(const Bitmap& bm) {
    RenderedPart out;
    out.kind = PartKind::Image;
    out.width = bm.width();
    out.height = bm.height();
    out.pixels.resize(static_cast<std::size_t>(bm.width()) * bm.height());

    const std::uint8_t* src = bm.pixels();
    const std::uint32_t rowPitch = bm.rowBytes();
    auto* dst = reinterpret_cast<std::uint8_t*>(out.pixels.data());
    const std::size_t rowCopy = static_cast<std::size_t>(bm.width()) * kBytesPerPixel;
    for (std::uint32_t y = 0; y < bm.height(); ++y) {
        std::memcpy(dst + static_cast<std::size_t>(y) * rowCopy,
                    src + static_cast<std::size_t>(y) * rowPitch,
                    rowCopy);
    }
    return out;
}

bool compose(const std::uint8_t* data, std::size_t len, RenderedMessage& out) {
    Reader r{data, len};
    std::vector<PartDesc> parts;
    std::vector<ImageDesc> images;
    if (!parse(r, parts, images)) return false;

    Arena arena{arena_size_for(images)};
    std::vector<Bitmap*> surfaces;
    surfaces.reserve(images.size());
    if (!decode_surfaces(arena, images, surfaces)) return false;

    out.parts.reserve(parts.size());
    for (const PartDesc& p : parts) {
        switch (p.kind) {
        case PartKind::Text:
        case PartKind::Reply: {
            RenderedPart rp;
            rp.kind = p.kind;
            rp.text = p.text;
            out.parts.push_back(std::move(rp));
            break;
        }
        case PartKind::Image: {
            Bitmap& bm = *surfaces[p.image_index];
            out.parts.push_back(render_image(bm));
            bm.~Bitmap();  // teardown: external storage is returned via its release callback
            break;
        }
        case PartKind::Sticker: {
            RenderedPart rp;
            rp.kind = PartKind::Sticker;
            rp.sticker_id = p.sticker.sticker_id;
            rp.palette = p.sticker.palette;
            out.parts.push_back(std::move(rp));
            break;
        }
        }
    }
    return true;
}

}  // namespace

bool compose_message(const std::uint8_t* data, std::size_t len, RenderedMessage& out) {
    out.parts.clear();
    if (data == nullptr || len < 8) return false;
    try {
        return compose(data, len, out);
    } catch (...) {
        out.parts.clear();
        return false;
    }
}

}  // namespace sasmedia
