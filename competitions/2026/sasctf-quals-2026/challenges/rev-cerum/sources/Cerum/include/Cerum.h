#pragma once

#include "IPlug_include_in_plug_hdr.h"
#include "IControls.h"

#if IPLUG_DSP
  #include "Cerum_DSP.h"
#endif

#include <atomic>
#include <thread>
#include <openssl/sha.h>

#include "startup.h"
#include "Note.h"
#include "ComputeShaderControl.h"
#include "xtea.h"
#include "globals.h"
#include "str_obfuscate.h"
#include "ptr_obfuscate.h"
#include "int_obfuscate.h"
#include "obfusheader.h"
#include "licensing_client.hpp"
#include "hwid.hpp"
#include "iohelp.hpp"
#include "rsa.h"

using namespace iplug;
using namespace igraphics;

class Cerum final : public Plugin
{
public:
  Cerum(const InstanceInfo& info);
  ~Cerum();

#if IPLUG_DSP // http://bit.ly/2S64BDd
public:
  void ProcessBlock(sample** inputs, sample** outputs, int nFrames) override;
  void ProcessMidiMsg(const IMidiMsg& msg) override;
  void OnReset() override;
  void OnIdle() override;
  bool OnMessage(int msgTag, int ctrlTag, int dataSize, const void* pData) override;
  void OnParamChange(int paramIdx) override;
  void CheckExistingLicense();
  void StartLicenseCheck(int notesCount);

  void LogToUI(const std::string& message);

  void OnHostIdentified();

  void Activate();
  void RealActivate();

  LicenseCheckerControl* computer = 0;

  static inline void (Cerum::*ActivationMethod)() = &Cerum::Activate;

private:
  void StartActivationThread();
  void SetActivationMode(bool isLicensed);
  CerumDSP<sample> mDSP{8};
  std::list<std::string> mLogMessages;
  bool pluginActivated = false;
  std::vector<Note> notes;
  IPeakAvgSender<2> mMeterSender;
  std::map<int, double> noteStartTimes;
  int licStartSeqPrevNote = 0;
  int licStartCount = 0;
  bool licCheckMode = 0;
  bool notesGathered = 0;
  bool loaded = 0;
  bool licrefDownloaded = 0;
  bool stopRequested = 0;
  std::atomic<bool> activationInProgress{false};
  std::thread activationThread;
  LicFile savedLicense;
#endif
};
