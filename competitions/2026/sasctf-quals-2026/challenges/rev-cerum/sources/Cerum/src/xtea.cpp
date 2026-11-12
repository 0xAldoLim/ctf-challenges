#pragma once

#include <int_obfuscate.h>
#include "xtea.h"
#include "globals.h"

void xtea_encrypt(unsigned int num_rounds, uint32_t v[2], uint32_t const k[4])
{
  unsigned int i;
  uint32_t v0 = v[0], v1 = v[1], sum = 0, delta = 0x9E3779B9;
  for (i = 0; i < num_rounds; i++)
  {
    v0 += (((v1 << 4) ^ (v1 >> 5)) + v1) ^ (sum + k[sum & 3]);
    sum += delta;
    v1 += (((v0 << 4) ^ (v0 >> 5)) + v0) ^ (sum + k[(sum >> 11) & 3]);
  }
  v[0] = v0;
  v[1] = v1;
}

void gen_key(char input, uint32_t* out_ptr)
{
  out_ptr[0] = (0x38a312d8 * input) & 0xFFFFFFFF;
  out_ptr[1] = (0x1701aac7 * input + 1337 * (input % 10)) & 0xFFFFFFFF;
  out_ptr[2] = (0x78007535 * (127 - input)) & 0xFFFFFFFF;
  out_ptr[3] = (0x53e7cafe * (127 - input) + 13337) & 0xFFFFFFFF;
}

void scramble_xtea(std::vector<Note>& notes, std::vector<Scrambled>& res)
{
  uint32_t key[4];

  for (int i = 0; i < notes.size(); i++)
  {
    gen_key(notes[i].noteId, key);

    uint32_t xoredTime = notes[i].duration ^ notes[i].startTime;
    uint32_t data[] = {
      ((((xoredTime >> 8) ^ cerum::globals::xor_key1) & 0xFF) << 24) | notes[i].duration,
      (((xoredTime ^ cerum::globals::xor_key2) & 0xFF) << 24) | notes[i].startTime
    };

    xtea_encrypt(16, data, key);

    res[i] = Scrambled(xoredTime, data[0], data[1]);
  }
}
