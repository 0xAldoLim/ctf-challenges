#pragma once

#include "note.h"
#include <stdint.h>
#include <vector>

void xtea_encrypt(unsigned int num_rounds, uint32_t v[2], uint32_t const k[4]);
void gen_key(char input, uint32_t* out_ptr);
void scramble_xtea(std::vector<Note>& notes, std::vector<Scrambled>& res);
