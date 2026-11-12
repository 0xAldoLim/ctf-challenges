cmake_minimum_required(VERSION 3.22.1)
project(sasmedia CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# libsasmedia.so — the Sasenger native message core. The challenge's 0-click
# attack surface is the "SMC1" container decoder in message.cpp (the single flaw
# is the stride-vs-width slip in pass-1 surface decode — see writeup/).
add_library(sasmedia SHARED
    sasmedia.cpp
    message.cpp)

target_compile_options(sasmedia PRIVATE -O2 -fno-omit-frame-pointer -Wall -Wextra)

# Android log for diagnostics during bring-up.
find_library(log-lib log)
target_link_libraries(sasmedia ${log-lib})
