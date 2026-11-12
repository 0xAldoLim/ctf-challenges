#pragma once

#include <cstddef>
#include <vector>

namespace cerum
{
void InflateBuffer(const char* compressed_data, std::size_t size, std::vector<char>& out_buffer);
void Startup();
void PostStartup();
} // namespace cerum
