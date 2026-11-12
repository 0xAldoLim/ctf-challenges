// bitmap.hpp — a decoded image surface (ARGB_8888), modeled on android::Bitmap.
//
// SPDX-License-Identifier: Proprietary
#pragma once

#include <cstdint>

namespace sasmedia {

// A decoded image surface: ARGB_8888 pixels plus geometry.
//
// The pixel-storage model mirrors Android's `android::Bitmap`: pixels are either
// owned by the surrounding decode arena (no per-surface cleanup) or *externally
// backed* — owned by something outside the arena, such as an mmap'd sticker asset
// or a zero-copy shared buffer — in which case the surface carries a release
// callback that is invoked exactly once at destruction to hand ownership back.
//
// Geometry is kept as explicit `width`/`height`/`rowBytes` (stride) rather than
// derived on the fly so that row-padded and sub-imaged surfaces share one type.
// `pixels[y * rowBytes + x * 4 ..]` addresses pixel (x, y).
//
// Surfaces are non-copyable: a surface uniquely owns its release responsibility.
class Bitmap {
public:
    // Signature matches the external-pixel free convention: release(pixels, ctx).
    using ReleaseFn = void (*)(void* pixels, void* context);

    // Arena-backed surface: pixels live in the decode arena and are reclaimed
    // with it; there is nothing to release per-surface.
    Bitmap(std::uint32_t width, std::uint32_t height,
           std::uint32_t rowBytes, std::uint8_t* pixels) noexcept
        : width_{width},
          height_{height},
          rowBytes_{rowBytes},
          storage_{Storage::Arena},
          pixels_{pixels},
          release_{nullptr},
          context_{nullptr} {}

    // Externally-backed surface: `release(pixels, context)` returns ownership of
    // the pixel memory at destruction.
    Bitmap(std::uint32_t width, std::uint32_t height,
           std::uint32_t rowBytes, std::uint8_t* pixels,
           ReleaseFn release, void* context) noexcept
        : width_{width},
          height_{height},
          rowBytes_{rowBytes},
          storage_{Storage::External},
          pixels_{pixels},
          release_{release},
          context_{context} {}

    ~Bitmap() {
        if (storage_ == Storage::External && release_ != nullptr) {
            release_(pixels_, context_);
        }
    }

    Bitmap(const Bitmap&) = delete;
    Bitmap& operator=(const Bitmap&) = delete;

    [[nodiscard]] std::uint32_t width() const noexcept { return width_; }
    [[nodiscard]] std::uint32_t height() const noexcept { return height_; }
    [[nodiscard]] std::uint32_t rowBytes() const noexcept { return rowBytes_; }

    [[nodiscard]] const std::uint8_t* pixels() const noexcept { return pixels_; }
    [[nodiscard]] std::uint8_t* pixels() noexcept { return pixels_; }

private:
    enum class Storage : std::uint32_t { Arena = 0, External = 1 };

    std::uint32_t width_;
    std::uint32_t height_;
    std::uint32_t rowBytes_;
    Storage       storage_;
    std::uint8_t* pixels_;
    ReleaseFn     release_;
    void*         context_;
};

}  // namespace sasmedia
