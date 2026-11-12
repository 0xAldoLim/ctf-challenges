#pragma once

#include <stdint.h>

#pragma pack(push, 1)
struct Note
{
  char noteId;
  unsigned long duration;
  unsigned long startTime;

public:
  Note() : Note(0, 0, 0) { }

  Note(char noteId, unsigned long duration, unsigned long startTime)
  {
    this->noteId = noteId;
    this->duration = duration;
    this->startTime = startTime;
  }

  bool operator==(const Note& other) const { return (noteId == other.noteId && duration == other.duration && startTime == other.startTime); }
};
#pragma pack(pop)

#pragma pack(push, 1)
struct Scrambled
{
  int32_t xoredTime;
  int32_t enc1;
  int32_t enc2;

  Scrambled() : Scrambled(0, 0, 0) { }

  Scrambled(int32_t xoredTime, int32_t enc1, int32_t enc2)
  {
    this->xoredTime = xoredTime;
    this->enc1 = enc1;
    this->enc2 = enc2;
  }
};
#pragma pack(pop)
