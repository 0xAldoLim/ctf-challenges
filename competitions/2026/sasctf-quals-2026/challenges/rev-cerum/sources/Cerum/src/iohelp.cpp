#include "iohelp.hpp"

#include <filesystem>
#include <fstream>

namespace fs = std::filesystem;

void LicFile::write() const
{
  fs::path path = std::getenv("APPDATA");
  path /= PLUGIN_DATA_DIR;

  fs::create_directories(path);

  path /= LIC_FILENAME;

  std::ofstream out(path, std::ios::binary);

  int32_t n_count = static_cast<int32_t>(notes.size());
  int32_t c_count = static_cast<int32_t>(checker.size());
  int32_t s_count = static_cast<int32_t>(signature.size());

  out.write(reinterpret_cast<const char*>(&n_count), sizeof(n_count));
  out.write(reinterpret_cast<const char*>(&c_count), sizeof(c_count));
  out.write(reinterpret_cast<const char*>(&s_count), sizeof(s_count));
  out.write(reinterpret_cast<const char*>(notes.data()), n_count * sizeof(Note));
  out.write(reinterpret_cast<const char*>(checker.data()), c_count);
  out.write(reinterpret_cast<const char*>(signature.data()), s_count);
}

void LicFile::read()
{
  fs::path path = std::getenv("APPDATA");
  path /= PLUGIN_DATA_DIR;

  path /= LIC_FILENAME;

  std::ifstream in(path, std::ios::binary);

  int32_t n_count;
  int32_t c_count;
  int32_t s_count;

  in.read(reinterpret_cast<char*>(&n_count), sizeof(n_count));
  in.read(reinterpret_cast<char*>(&c_count), sizeof(c_count));
  in.read(reinterpret_cast<char*>(&s_count), sizeof(s_count));

  notes.resize(static_cast<size_t>(n_count));
  checker.resize(static_cast<size_t>(c_count));
  signature.resize(static_cast<size_t>(s_count));

  in.read(reinterpret_cast<char*>(notes.data()), notes.size() * sizeof(Note));
  in.read(reinterpret_cast<char*>(checker.data()), checker.size());
  in.read(reinterpret_cast<char*>(signature.data()), signature.size());
}

bool LicFile::exists()
{
  fs::path path = std::getenv("APPDATA");
  path /= PLUGIN_DATA_DIR;

  path /= LIC_FILENAME;

  return fs::exists(path);
}

void WriteDataFile(const char* filename, const void* data, int size)
{
  fs::path path = std::getenv("APPDATA");
  path /= PLUGIN_DATA_DIR;

  fs::create_directories(path);

  path /= filename;

  std::ofstream file(path, std::ios::out | std::ios::binary);
  file.write((char*)data, size);
}

int ReadDataFile(const char* filename, void* data, int size)
{
  fs::path path = std::getenv("APPDATA");
  path /= PLUGIN_DATA_DIR;
  path /= filename;

  if (!fs::exists(path))
    return -1;

  std::ifstream file(path, std::ios::in | std::ios::binary);
  file.read((char*)data, size);

  return 0;
}

int ReadDataFile(const char* filename, std::vector<char>& data)
{
  fs::path path = std::getenv("APPDATA");
  path /= PLUGIN_DATA_DIR;
  path /= filename;

  if (!fs::exists(path))
    return -1;

  std::ifstream file(path, std::ios::in | std::ios::binary);
  size_t size = file.tellg();
  data.resize(size);
  file.read(data.data(), size);

  return 0;
}
