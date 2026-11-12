#pragma once

#include <cstdint>
#include <intrin.h>
#include <limits>

#pragma intrinsic(_ReadWriteBarrier)

namespace ctobf
{
namespace detail
{

static_assert(sizeof(std::int32_t) == sizeof(std::uint32_t));
static_assert(std::numeric_limits<std::uint32_t>::digits == 32);

[[nodiscard]] constexpr std::uint32_t rotl32(std::uint32_t x, unsigned r) noexcept
{
  r &= 31u;
  return (r == 0u) ? x : static_cast<std::uint32_t>((x << r) | (x >> (32u - r)));
}

[[nodiscard]] constexpr std::uint32_t rotr32(std::uint32_t x, unsigned r) noexcept
{
  r &= 31u;
  return (r == 0u) ? x : static_cast<std::uint32_t>((x >> r) | (x << (32u - r)));
}

[[nodiscard]] constexpr std::uint32_t mix32(std::uint32_t x) noexcept
{
  x ^= x >> 16u;
  x *= 0x7feb352du;
  x ^= x >> 15u;
  x *= 0x846ca68bu;
  x ^= x >> 16u;
  return x;
}

[[nodiscard]] constexpr std::uint32_t make_seed(std::uint32_t line, std::uint32_t counter) noexcept
{
  return mix32(0xc2b2ae35u ^ static_cast<std::uint32_t>(line * 0x9e3779b9u) ^ static_cast<std::uint32_t>(counter * 0x85ebca6bu));
}

[[nodiscard]] constexpr std::uint32_t to_u32(std::int32_t x) noexcept { return static_cast<std::uint32_t>(x); }

[[nodiscard]] constexpr std::int32_t from_u32(std::uint32_t x) noexcept { return static_cast<std::int32_t>(x); }

[[nodiscard]] constexpr std::uint32_t derive_b0(std::uint32_t seed) noexcept { return mix32(seed ^ 0x243f6a88u); }

[[nodiscard]] constexpr std::uint32_t derive_b1(std::uint32_t seed) noexcept { return mix32(seed ^ 0x85a308d3u); }

[[nodiscard]] constexpr std::uint32_t derive_b2(std::uint32_t seed) noexcept { return mix32(seed ^ 0x13198a2eu); }

[[nodiscard]] constexpr std::uint32_t derive_g(std::uint32_t seed) noexcept { return mix32(seed ^ 0x03707344u); }

[[nodiscard]] constexpr std::uint32_t encrypt(std::uint32_t plain, std::uint32_t k0, std::uint32_t k1, std::uint32_t k2) noexcept
{
  std::uint32_t x = plain;
  x ^= k0;
  x = rotl32(static_cast<std::uint32_t>(x + k1), 9u);
  x ^= k2;
  x = rotl32(static_cast<std::uint32_t>(x + 0xa5a5a5a5u), 17u);
  return x;
}

[[nodiscard]] constexpr std::uint32_t decrypt(std::uint32_t cipher, std::uint32_t k0, std::uint32_t k1, std::uint32_t k2) noexcept
{
  std::uint32_t x = cipher;
  x = static_cast<std::uint32_t>(rotr32(x, 17u) - 0xa5a5a5a5u);
  x ^= k2;
  x = static_cast<std::uint32_t>(rotr32(x, 9u) - k1);
  x ^= k0;
  return x;
}

[[nodiscard]] constexpr std::uint32_t make_data(std::int32_t value, std::uint32_t line, std::uint32_t counter) noexcept
{
  std::uint32_t seed = make_seed(line, counter);
  std::uint32_t b0 = derive_b0(seed);
  std::uint32_t b1 = derive_b1(seed);
  std::uint32_t b2 = derive_b2(seed);
  std::uint32_t g = derive_g(seed);

  std::uint32_t k0 = b0 ^ g;
  std::uint32_t k1 = static_cast<std::uint32_t>(b1 + rotl32(g, 5u));
  std::uint32_t k2 = b2 ^ rotr32(g, 7u);

  return encrypt(to_u32(value), k0, k1, k2);
}

[[nodiscard]] constexpr std::uint32_t make_check(std::int32_t value, std::uint32_t line, std::uint32_t counter) noexcept
{
  std::uint32_t seed = make_seed(line, counter);
  std::uint32_t b0 = derive_b0(seed);
  std::uint32_t g = derive_g(seed);
  std::uint32_t data = make_data(value, line, counter);

  return g ^ mix32(static_cast<std::uint32_t>(data + b0));
}

[[nodiscard]] __declspec(noinline) inline std::uint32_t opaque(std::uint32_t value) noexcept
{
  _ReadWriteBarrier();

  volatile std::uint32_t tmp = value;

  _ReadWriteBarrier();

  return tmp;
}

} // namespace detail

class int32 final
{
public:
  constexpr int32(std::int32_t value, std::uint32_t line, std::uint32_t counter) noexcept
    : b0_(detail::derive_b0(detail::make_seed(line, counter)))
    , b1_(detail::derive_b1(detail::make_seed(line, counter)))
    , b2_(detail::derive_b2(detail::make_seed(line, counter)))
    , data_(detail::make_data(value, line, counter))
    , check_(detail::make_check(value, line, counter))
  {
  }

  [[nodiscard]] std::int32_t value() const noexcept
  {
    std::uint32_t b0 = detail::opaque(b0_);
    std::uint32_t b1 = detail::opaque(b1_);
    std::uint32_t b2 = detail::opaque(b2_);
    std::uint32_t data = detail::opaque(data_);
    std::uint32_t check = detail::opaque(check_);

    std::uint32_t g = check ^ detail::mix32(static_cast<std::uint32_t>(data + b0));

    std::uint32_t k0 = b0 ^ g;
    std::uint32_t k1 = static_cast<std::uint32_t>(b1 + detail::rotl32(g, 5u));
    std::uint32_t k2 = b2 ^ detail::rotr32(g, 7u);

    std::uint32_t plain = detail::decrypt(data, k0, k1, k2);

    return detail::from_u32(plain);
  }

  [[nodiscard]] operator std::int32_t() const noexcept { return value(); }

private:
  const std::uint32_t b0_;
  const std::uint32_t b1_;
  const std::uint32_t b2_;
  const std::uint32_t data_;
  const std::uint32_t check_;
};

} // namespace ctobf

#define CTOBF_INT32(value) (::ctobf::int32{static_cast<std::int32_t>(value), static_cast<std::uint32_t>(__LINE__), static_cast<std::uint32_t>(__COUNTER__)})
