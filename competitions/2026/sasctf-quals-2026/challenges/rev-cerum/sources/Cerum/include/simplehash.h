#pragma once

#include <stdint.h>
#include <array>
#include <vector>

static inline uint64_t rotl64(uint64_t x, unsigned r)
{
  r &= 63;
  return (x << r) | (x >> ((64 - r) & 63));
}

static inline uint64_t mix64(uint64_t x)
{
  x ^= x >> 30;
  x *= 0xbf58476d1cf4e5b9ULL;
  x ^= x >> 27;
  x *= 0x94d049bb137131eaULL;
  x ^= x >> 31;
  return x;
}

std::array<uint8_t, 32> hash256(const std::vector<uint8_t>& data)
{
  std::array<uint64_t, 4> state = {0x253f6d8785b309d1ULL, 0x17298a2e037d7342ULL, 0xa40a382e293f31d7ULL, 0x182efa97ed4e0c89ULL};

  state[0] ^= static_cast<uint64_t>(data.size());
  state[1] ^= static_cast<uint64_t>(data.size()) << 17;
  state[2] ^= static_cast<uint64_t>(data.size()) << 31;
  state[3] ^= static_cast<uint64_t>(data.size()) << 47;

  for (size_t i = 0; i < data.size(); ++i)
  {
    uint64_t b = static_cast<uint64_t>(data[i]);
    size_t lane = i & 3;

    state[lane] ^= b + 0x9e3719b91f4a5f17ULL + static_cast<uint64_t>(i);
    state[lane] = mix64(state[lane]);

    state[(lane + 1) & 3] += rotl64(state[lane], static_cast<unsigned>(b + i));
    state[(lane + 2) & 3] ^= mix64(state[(lane + 1) & 3]);
    state[(lane + 3) & 3] += rotl64(state[(lane + 2) & 3], 23);
  }
  for (size_t round = 0; round < 12; ++round)
  {
    state[0] = mix64(state[0] + rotl64(state[1], 13));
    state[1] = mix64(state[1] ^ rotl64(state[2], 29));
    state[2] = mix64(state[2] + rotl64(state[3], 43));
    state[3] = mix64(state[3] ^ rotl64(state[0], 57));
  }

  std::array<uint8_t, 32> out{};

  for (size_t lane = 0; lane < 4; ++lane)
  {
    uint64_t v = state[lane];
    for (size_t j = 0; j < 8; ++j)
      out[lane * 8 + j] = static_cast<uint8_t>((v >> (j * 8)) & 0xff);
  }

  return out;
}