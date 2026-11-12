cmake_minimum_required(VERSION 3.14)
project(Cerum VERSION 1.0.0)

if(NOT DEFINED IPLUG2_DIR)
  set(IPLUG2_DIR "${CMAKE_CURRENT_SOURCE_DIR}/../.." CACHE PATH "iPlug2 root directory")
endif()

include(${IPLUG2_DIR}/iPlug2.cmake)
find_package(iPlug2 REQUIRED)

iplug_add_plugin(${PROJECT_NAME}
  SOURCES
    src/Cerum.cpp
    src/ComputeShaderControl.cpp
    src/Globals.cpp
    src/Startup.cpp
    src/licensing_client.cpp
    src/xtea.cpp
    include/Cerum.h
    include/Cerum_DSP.h
    include/ComputeShaderControl.h
    include/globals.h
    include/startup.h
    include/licensing_client.hpp
    include/xtea.h
    resources/resource.h
  RESOURCES
    resources/fonts/Roboto-Regular.ttf
  LINK
    iPlug2::Extras::Synth
)

target_include_directories(${PROJECT_NAME} PRIVATE
  ${CMAKE_CURRENT_SOURCE_DIR}/include
  ${CMAKE_CURRENT_SOURCE_DIR}/dependencies/zlib
)
