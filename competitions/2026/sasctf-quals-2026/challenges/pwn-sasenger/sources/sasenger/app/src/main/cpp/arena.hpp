// arena.hpp — bump-pointer arena for a single message decode.
//
// SPDX-License-Identifier: Proprietary
#pragma once

#include <cstddef>
#include <cstdint>
#include <new>
#include <utility>

namespace sasmedia {

// A bump-pointer arena scoped to the decoding of one inbound message.
//
// Every decode allocation — pixel buffers and `Bitmap` headers alike — is carved
// sequentially from one contiguous region and released together when the arena
// goes out of scope. Two properties motivate this over the process allocator:
//
//   * Locality: a message's surfaces are decoded, composited, and torn down as a
//     unit, so a single contiguous region is both faster and simpler to reason
//     about than scattering short-lived buffers across the global heap.
//   * Determinism: sequential allocations are placed adjacently, which the
//     compositor relies on when it walks a message's surfaces in order.
//
// The arena does not free individual allocations and does not run destructors —
// callers that place non-trivially-destructible objects here are responsible for
// destroying them (see Compositor). It is a region, not a general allocator.
class Arena {
public:
    explicit Arena(std::size_t capacity)
        : capacity_{capacity},
          base_{static_cast<std::byte*>(::operator new(capacity))},
          offset_{0} {}

    ~Arena() { ::operator delete(base_); }

    Arena(const Arena&) = delete;
    Arena& operator=(const Arena&) = delete;
    Arena(Arena&&) = delete;
    Arena& operator=(Arena&&) = delete;

    // Carve `size` bytes at `alignment`. Returns nullptr when the region is
    // exhausted; callers must check and fail the decode cleanly rather than
    // assume success.
    [[nodiscard]] void* allocate(std::size_t size,
                                 std::size_t alignment = alignof(std::max_align_t)) noexcept {
        const std::size_t aligned = align_up(offset_, alignment);
        // Overflow-safe bounds check: `aligned` and `aligned + size` must both
        // fit within the region.
        if (aligned > capacity_ || size > capacity_ - aligned) {
            return nullptr;
        }
        offset_ = aligned + size;
        return base_ + aligned;
    }

    // Arena-construct a `T`. The object is *not* destroyed when the arena is
    // released, so `T` must be trivially destructible or be torn down explicitly
    // by the owner.
    template <typename T, typename... Args>
    [[nodiscard]] T* create(Args&&... args) {
        void* const slot = allocate(sizeof(T), alignof(T));
        return slot ? ::new (slot) T(std::forward<Args>(args)...) : nullptr;
    }

    [[nodiscard]] std::size_t used() const noexcept { return offset_; }
    [[nodiscard]] std::size_t capacity() const noexcept { return capacity_; }

private:
    static constexpr std::size_t align_up(std::size_t n, std::size_t a) noexcept {
        return (n + (a - 1)) & ~(a - 1);
    }

    std::size_t capacity_;
    std::byte*  base_;
    std::size_t offset_;
};

}  // namespace sasmedia
