// message.hpp — inbound message container: parse + two-pass composite.
//
// SPDX-License-Identifier: Proprietary
#pragma once

#include <cstddef>
#include <cstdint>
#include <string>
#include <vector>

namespace sasmedia {

// Wire format — "SMC1" (Sasenger Message Container, version 1, little-endian).
//
//   header     'S' 'M' 'C' '1' | u8 version=1 | u8 flags=0 | u16 part_count
//   part[i]    u8 kind | <kind-specific body>
//     TEXT(1)     u32 len | u8 utf8[len]
//     IMAGE(2)    u16 width | u16 height | u32 row_bytes | u32 data_len | u8 data[data_len]
//     STICKER(3)  u16 sticker_id | u16 n | u32 rgba[n]
//     REPLY(4)    u32 len | u8 utf8[len]      (a quote of the message replied to)
//
// A message is a *container*: it carries any number of parts in display order,
// including multiple images. STICKER palettes are display tint only; a REPLY part
// (conventionally first) is a quote snippet rendered as a header.
enum class PartKind : std::uint8_t { Text = 1, Image = 2, Sticker = 3, Reply = 4 };

// One composited part, ready for the UI. Holds heap copies that outlive the
// transient per-message decode arena.
struct RenderedPart {
    PartKind kind{};
    std::string text;                       // Text
    std::uint32_t width = 0;                // Image
    std::uint32_t height = 0;               // Image
    std::vector<std::uint32_t> pixels;      // Image: ARGB_8888, width*height
    int sticker_id = -1;                    // Sticker
    std::vector<std::uint32_t> palette;     // Sticker: RGBA tint colors (UI only)
};

struct RenderedMessage {
    std::vector<RenderedPart> parts;
};

// Decode one inbound "SMC1" container into display-ready parts. Returns false on
// a malformed container (and leaves `out` empty). Never throws.
//
// This is the messenger's 0-click attack surface: it runs automatically on every
// inbound message, on untrusted bytes. See message.cpp.
bool compose_message(const std::uint8_t* data, std::size_t len, RenderedMessage& out);

}  // namespace sasmedia
