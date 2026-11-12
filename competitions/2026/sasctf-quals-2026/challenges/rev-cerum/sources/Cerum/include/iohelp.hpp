#pragma once

#include "globals.h"
#include "Note.h"

class LicFile
{
public:
  std::vector<Note> notes;
  std::vector<uint8_t> checker;
  std::vector<uint8_t> signature;

  void write() const;
  void read();
  bool exists();
};

void WriteDataFile(const char* filename, const void* data, int size);

int ReadDataFile(const char* filename, void* data, int size);

int ReadDataFile(const char* filename, std::vector<char>& data);

