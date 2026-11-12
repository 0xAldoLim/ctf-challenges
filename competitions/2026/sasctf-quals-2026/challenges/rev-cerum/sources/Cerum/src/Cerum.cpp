#include "Cerum.h"
#include "IPlug_include_in_plug_src.h"

// #define DEBUG

Cerum::Cerum(const InstanceInfo& info) : iplug::Plugin(info, MakeConfig(kNumParams, 1))
{
  std::function panDisplayFunction = [](double value, WDL_String& text) {
    if (value < -0.01)
      text.SetFormatted(16, "%d%%", (int)std::abs(value));
    else if (value > 0.01)
      text.SetFormatted(16, "%d%%", (int)(value));
    else
      text.SetFormatted(16, "Center");
  };

  GetParam(kParamMaster)->InitDouble("Master", 0.8, 0.0, 1.0, 0.01, "");
  GetParam(kParamDrive)->InitDouble("Drive", 0.15, 0.0, 1.0, 0.01, "");
  GetParam(kParamLimiterCeiling)->InitDouble("Limiter", 0.95, 0.5, 1.0, 0.01, "");
  GetParam(kParamAttack)->InitDouble("Attack", 10.0, 1.0, 5000.0, 0.1, "ms", IParam::kFlagsNone, "ADSR", IParam::ShapePowCurve(3.));
  GetParam(kParamDecay)->InitDouble("Decay", 140.0, 100.0, 5000.0, 0.1, "ms", IParam::kFlagsNone, "ADSR", IParam::ShapePowCurve(3.));
  GetParam(kParamSustain)->InitDouble("Sustain", 0.75, 0.0, 100.0, 0.1, "%", IParam::kFlagsNone, "ADSR");
  GetParam(kParamRelease)->InitDouble("Release", 280.0, 10.0, 8000.0, 0.1, "ms", IParam::kFlagsNone, "ADSR", IParam::ShapePowCurve(3.));

  GetParam(kParamOsc1Gain)->InitDouble("Osc 1 Gain", 0.8, 0.0, 1.0, 0.01, "");
  GetParam(kParamOsc1Wave)->InitEnum("Osc 1 Wave", CerumDSP<sample>::kWaveSine, {"Sine", "Tri", "Saw", "Square"});
  GetParam(kParamOsc1Octave)->InitInt("Osc 1 Octave", 0, -2, 2, "oct");
  GetParam(kParamOsc1Detune)->InitDouble("Osc 1 Detune", 0.0, -24.0, 24.0, 0.1, "ct");
  GetParam(kParamOsc1Pan)->InitDouble("Osc 1 Pan", 0.0, -100.0, 100.0, 1.0, "", 0, "", IParam::ShapeLinear(), IParam::EParamUnit::kUnitPan, panDisplayFunction);

  GetParam(kParamOsc2Gain)->InitDouble("Osc 2 Gain", 0.0, 0.0, 1.0, 0.01, "");
  GetParam(kParamOsc2Wave)->InitEnum("Osc 2 Wave", CerumDSP<sample>::kWaveSine, {"Sine", "Tri", "Saw", "Square"});
  GetParam(kParamOsc2Octave)->InitInt("Osc 2 Octave", 0, -2, 2, "oct");
  GetParam(kParamOsc2Detune)->InitDouble("Osc 2 Detune", 0, -24.0, 24.0, 0.1, "ct");
  GetParam(kParamOsc2Pan)->InitDouble("Osc 2 Pan", 0.0, -100.0, 100.0, 1.0, "", 0, "", IParam::ShapeLinear(), IParam::EParamUnit::kUnitPan, panDisplayFunction);

  GetParam(kParamOsc3Gain)->InitDouble("Osc 3 Gain", 0.0, 0.0, 1.0, 0.01, "");
  GetParam(kParamOsc3Wave)->InitEnum("Osc 3 Wave", CerumDSP<sample>::kWaveSine, {"Sine", "Tri", "Saw", "Square"});
  GetParam(kParamOsc3Octave)->InitInt("Osc 3 Octave", 0, -2, 2, "oct");
  GetParam(kParamOsc3Detune)->InitDouble("Osc 3 Detune", 0, -24.0, 24.0, 0.1, "ct");
  GetParam(kParamOsc3Pan)->InitDouble("Osc 3 Pan", 0.0, -100.0, 100.0, 1.0, "", 0, "", IParam::ShapeLinear(), IParam::EParamUnit::kUnitPan, panDisplayFunction);

  GetParam(kParamGlideTime)->InitDouble("Glide", 0.0, 0.0, 300.0, 0.5, "ms", 0, "", IParam::ShapePowCurve(3.));

#if IPLUG_EDITOR // http://bit.ly/2S64BDd
  mMakeGraphicsFunc = [&]() { return MakeGraphics(*this, PLUG_WIDTH, PLUG_HEIGHT, PLUG_FPS, GetScaleForScreen(PLUG_WIDTH, PLUG_HEIGHT)); };

  printf("JUCE Framework 8.0.8");

  mLayoutFunc = [&](IGraphics* pGraphics) {
    const IRECT keyboardBounds = IRECT(10.f, 240.f, 790.f, 410.f);

    const IVStyle DEFAULT_STYLE{
      true, // Show label
      true, // Show value
      {
        IColor(255, 31, 31, 31),                                                        // Background
        IColor(0, 0, 0, 255),                                                           // Foreground
        IColor(255, 48, 48, 48),                                                        // Pressed
        IColor(255, 31, 31, 31),                                                        // Frame
        DEFAULT_HLCOLOR,                                                                // Highlight
        DEFAULT_SHCOLOR,                                                                // Shadow
        COLOR_GREEN,                                                                    // Extra 1
        DEFAULT_X2COLOR,                                                                // Extra 2
        DEFAULT_X3COLOR                                                                 // Extra 3
      },                                                                                // Colors
      IText(18.0, COLOR_WHITE, "Roboto-Regular", EAlign::Center, EVAlign::Top, 0.0),    // Label text
      IText(18.0, COLOR_WHITE, "Roboto-Regular", EAlign::Center, EVAlign::Bottom, 0.0), // Value text
      true,                                                                             // Hide cursor
      false,                                                                             // Draw frame
      false,                                                                             // Draw shadows
      false,                                                                            // Emboss
      0.0,                                                                              // Roundness
      1.0,                                                                              // Frame thickness
      3.0,                                                                              // Shadow offset
      1.0,                                                                              // Widget frac
      0.0                                                                               // Angle
    };

    const IVStyle HEADER_STYLE{
      true, // Show label
      true, // Show value
      {
        IColor(255, 31, 31, 31),                                                        // Background
        IColor(255, 255, 255, 255),                                                     // Foreground
        DEFAULT_PRCOLOR,                                                                // Pressed
        IColor(255, 31, 31, 31),                                                        // Frame
        DEFAULT_HLCOLOR,                                                                // Highlight
        DEFAULT_SHCOLOR,                                                                // Shadow
        IColor(255, 31, 31, 31),                                                        // Extra 1
        DEFAULT_X2COLOR,                                                                // Extra 2
        DEFAULT_X3COLOR                                                                 // Extra 3
      },                                                                                // Colors
      IText(16.0, COLOR_WHITE, "Roboto-Regular", EAlign::Center, EVAlign::Top, 0.0),    // Label text
      IText(28.0, COLOR_WHITE, "Roboto-Regular", EAlign::Center, EVAlign::Bottom, 0.0), // Value text
      true,                                                                             // Hide cursor
      true,                                                                             // Draw frame
      true,                                                                             // Draw shadows
      false,                                                                            // Emboss
      0.0,                                                                              // Roundness
      1.0,                                                                              // Frame thickness
      3.0,                                                                              // Shadow offset
      1.0,                                                                              // Widget frac
      0.0                                                                               // Angle
    };

    const IVStyle COMPACT_STYLE{
      true, // Show label
      true, // Show value
      {
        IColor(255, 31, 31, 31),                                                        // Background
        IColor(255, 255, 255, 255),                                                     // Foreground
        DEFAULT_PRCOLOR,                                                                // Pressed
        IColor(255, 31, 31, 31),                                                        // Frame
        DEFAULT_HLCOLOR,                                                                // Highlight
        DEFAULT_SHCOLOR,                                                                // Shadow
        COLOR_GREEN,                                                                    // Extra 1
        DEFAULT_X2COLOR,                                                                // Extra 2
        DEFAULT_X3COLOR                                                                 // Extra 3
      },                                                                                // Colors
      IText(14.0, COLOR_WHITE, "Roboto-Regular", EAlign::Center, EVAlign::Top, 0.0),    // Label text
      IText(14.0, COLOR_WHITE, "Roboto-Regular", EAlign::Center, EVAlign::Bottom, 0.0), // Value text
      true,                                                                             // Hide cursor
      true,                                                                             // Draw frame
      true,                                                                             // Draw shadows
      false,                                                                            // Emboss
      0.0,                                                                              // Roundness
      1.0,                                                                              // Frame thickness
      3.0,                                                                              // Shadow offset
      1.0,                                                                              // Widget frac
      0.0                                                                               // Angle
    };

    const IVStyle METER_STYLE{
      true, // Show label
      false, // Show value
      {
        IColor(255, 255, 255, 255),                                                     // Background
        IColor(255, 255, 255, 255),                                                     // Foreground
        IColor(255, 255, 255, 255),                                                     // Pressed
        IColor(255, 255, 255, 255),                                                     // Frame
        IColor(255, 255, 255, 255),                                                     // Highlight
        IColor(255, 255, 255, 255),                                                     // Shadow
        IColor(255, 255, 255, 255),                                                     // Extra 1
        IColor(255, 255, 255, 255),                                                     // Extra 2
        IColor(255, 255, 255, 255)                                                      // Extra 3
      },                                                                                // Colors
      IText(16.0, COLOR_WHITE, "Roboto-Regular", EAlign::Center, EVAlign::Top, 0.0),    // Label text
      IText(28.0, COLOR_WHITE, "Roboto-Regular", EAlign::Center, EVAlign::Bottom, 0.0), // Value text
      true,                                                                             // Hide cursor
      false,                                                                             // Draw frame
      false,                                                                             // Draw shadows
      false,                                                                            // Emboss
      1.0,                                                                              // Roundness
      1.0,                                                                              // Frame thickness
      0.0,                                                                              // Shadow offset
      1.0,                                                                              // Widget frac
      0.0                                                                               // Angle
    };

    pGraphics->AttachCornerResizer(EUIResizerMode::Scale, false);
    pGraphics->AttachPanelBackground(IColor(255, 31, 31, 31));
    pGraphics->EnableMouseOver(true);
    pGraphics->EnableMultiTouch(true);

    pGraphics->LoadFont("Roboto-Regular", ROBOTO_FN);

    IVKeyboardControl* keyboard = new IVKeyboardControl(keyboardBounds, 48, 84, false);
    keyboard->SetShowNotesAndVelocity(false);

    pGraphics->AttachControl(keyboard, keyboardControl);

    auto attachOscillatorControls = [&](const IRECT& panel, int oscIndex, int gainParam, int waveParam, int octaveParam, int detuneParam, int panParam,
                                        int gainTag, int waveTag, int octaveTag, int detuneTag, int panTag) {
      const auto name = std::string("OSC ") + std::to_string(oscIndex + 1);
      const IRECT waveRect = IRECT(panel.L + 6.f, panel.T + 26.f, panel.R - 6.f, panel.T + 58.f);
      const IRECT gainRect = IRECT(panel.L + 8.f, panel.T + 60.f, panel.L + 68.f, panel.T + 120.f);
      const IRECT octaveRect = IRECT(panel.L + 77.f, panel.T + 60.f, panel.L + 137.f, panel.T + 120.f);
      const IRECT detuneRect = IRECT(panel.L + 8.f, panel.T + 124.f, panel.L + 68.f, panel.T + 184.f);
      const IRECT panRect = IRECT(panel.L + 77.f, panel.T + 124.f, panel.L + 137.f, panel.T + 184.f);
      pGraphics->AttachControl(new IVLabelControl(panel.GetFromTop(24.f), name.c_str(), HEADER_STYLE));
      pGraphics->AttachControl(new IVTabSwitchControl(waveRect, waveParam, {"Sin", "Tri", "Saw", "Sq"}, "", DEFAULT_STYLE, EVShape::Rectangle, EDirection::Horizontal), waveTag);
      pGraphics->AttachControl(new IVKnobControl(gainRect, gainParam, "Gain", COMPACT_STYLE), gainTag);
      pGraphics->AttachControl(new IVKnobControl(octaveRect, octaveParam, "Oct", COMPACT_STYLE, false, false, -135.0, 135.0, 0.0), octaveTag);
      pGraphics->AttachControl(new IVKnobControl(detuneRect, detuneParam, "Det", COMPACT_STYLE, false, false, -135.0, 135.0, 0.0), detuneTag);
      pGraphics->AttachControl(new IVKnobControl(panRect, panParam, "Pan", COMPACT_STYLE, false, false, -135.0, 135.0, 0.0), panTag);
    };

    attachOscillatorControls(IRECT(20.f, 18.f, 165.f, 190.f), 0, kParamOsc1Gain, kParamOsc1Wave, kParamOsc1Octave, kParamOsc1Detune, kParamOsc1Pan,
                             osc1GainControl, osc1WaveControl, osc1OctaveControl, osc1DetuneControl, osc1PanControl);
    attachOscillatorControls(IRECT(175.f, 18.f, 320.f, 190.f), 1, kParamOsc2Gain, kParamOsc2Wave, kParamOsc2Octave, kParamOsc2Detune, kParamOsc2Pan,
                             osc2GainControl, osc2WaveControl, osc2OctaveControl, osc2DetuneControl, osc2PanControl);
    attachOscillatorControls(IRECT(330.f, 18.f, 475.f, 190.f), 2, kParamOsc3Gain, kParamOsc3Wave, kParamOsc3Octave, kParamOsc3Detune, kParamOsc3Pan,
                             osc3GainControl, osc3WaveControl, osc3OctaveControl, osc3DetuneControl, osc3PanControl);

    const IRECT envArea = IRECT(485.f, 18.f, 645.f, 190.f);

    pGraphics->AttachControl(new IVLabelControl(envArea.GetFromTop(24.f), "ENV", HEADER_STYLE));
    pGraphics->AttachControl(new IVSliderControl(envArea.GetGridCell(0, 0, 1, 4).GetTranslated(0.f, 26.f).GetMidHPadded(20.f), kParamAttack, "Atk", COMPACT_STYLE, false, EDirection::Vertical, DEFAULT_GEARING, 8.0, 2.0, false), attackControl);
    pGraphics->AttachControl(new IVSliderControl(envArea.GetGridCell(0, 1, 1, 4).GetTranslated(0.f, 26.f).GetMidHPadded(20.f), kParamDecay, "Dec", COMPACT_STYLE, false, EDirection::Vertical, DEFAULT_GEARING, 8.0, 2.0, false), decayControl);
    pGraphics->AttachControl(new IVSliderControl(envArea.GetGridCell(0, 2, 1, 4).GetTranslated(0.f, 26.f).GetMidHPadded(20.f), kParamSustain, "Sus", COMPACT_STYLE, false, EDirection::Vertical, DEFAULT_GEARING, 8.0, 2.0, false), sustainControl);
    pGraphics->AttachControl(new IVSliderControl(envArea.GetGridCell(0, 3, 1, 4).GetTranslated(0.f, 26.f).GetMidHPadded(20.f), kParamRelease, "Rel", COMPACT_STYLE, false, EDirection::Vertical, DEFAULT_GEARING, 8.0, 2.0, false), releaseControl);

    const IRECT masterParamsArea = IRECT(655.f, 18.f, 770.f, 190.f);

    pGraphics->AttachControl(new IVSliderControl(
      masterParamsArea.GetGridCell(0, 0, 1, 3).GetTranslated(0.f, 64.f).GetMidHPadded(15.f).GetReducedFromBottom(38.f), kParamMaster, "Master",
      COMPACT_STYLE, false, EDirection::Vertical, DEFAULT_GEARING, 8.0, 2.0, false), masterGain);
    pGraphics->AttachControl(new IVSliderControl(
      masterParamsArea.GetGridCell(0, 1, 1, 3).GetTranslated(0.f, 64.f).GetMidHPadded(15.f).GetReducedFromBottom(38.f), kParamDrive, "Drive",
      COMPACT_STYLE, false, EDirection::Vertical, DEFAULT_GEARING, 8.0, 2.0, false), driveGain);
    pGraphics->AttachControl(new IVSliderControl(
      masterParamsArea.GetGridCell(0, 2, 1, 3).GetTranslated(0.f, 64.f).GetMidHPadded(15.f).GetReducedFromBottom(38.f), kParamLimiterCeiling, "Limit",
      COMPACT_STYLE, false, EDirection::Vertical, DEFAULT_GEARING, 8.0, 2.0, false), limiterCeilingControl);
    pGraphics->AttachControl(new IVLabelControl(IRECT(655.f, 18.f, 770.f, 42.f), "Cerum", HEADER_STYLE));
    pGraphics->AttachControl(new IVLabelControl(IRECT(655.f, 44.f, 770.f, 68.f), OBF("TRIAL MODE"), COMPACT_STYLE), modeDisplayText);
    
    pGraphics->AttachControl(new IVLEDMeterControl<2>(IRECT(800.f, 10.f, 830.f, 370.f), "Out", METER_STYLE, EDirection::Vertical, {}), meterControl);
    pGraphics->AttachControl(
      new IVKnobControl(IRECT(790.f, 370.f, 840.f, 420.f), kParamGlideTime, "Glide", COMPACT_STYLE), glideTimeControl);

#ifdef DEBUG
    pGraphics->AttachControl(new IMultiLineTextControl(IRECT(20.f, 20.f, 700.f, 330.f), "Log starting...", IText(14, COLOR_WHITE, "Roboto-Regular")), logDisplay);

    pGraphics->AttachControl(new IVButtonControl(
                               IRECT(20.f, 210.f, 120.f, 240.f),
                               [this](IControl* pCaller) {
        CheckExistingLicense();
    }, "debug"), debugBtn);
#endif

    this->computer = new LicenseCheckerControl(IRECT(0.0, 0.0, 1.0, 1.0), [this, pGraphics](LicenseCheckerControl* control) {
      size_t count = notes.size();

      std::vector<int32_t> outputVector1(count), outputVector2(count);
      if (control->CopyLastGpuResult(outputVector1.data(), outputVector2.data(), count))
      {
        if (!licCheckMode)
        {
          unsigned char sha_buffer[32];

          SHA256_CTX ctx;
          SHA256_Init(&ctx);
          SHA256_Update(&ctx, outputVector1.data(), outputVector1.size() * sizeof(int));
          SHA256_Update(&ctx, outputVector2.data(), outputVector2.size() * sizeof(int));
          SHA256_Final(sha_buffer, &ctx);

          if (memcmp(sha_buffer, savedLicense.checker.data(), 32) == 0
              && verify_sign(cerum::globals::lic_key, savedLicense.checker.data(), savedLicense.checker.size(), savedLicense.signature.data(), savedLicense.signature.size()))
          {
            SetActivationMode(true);
          }
        }
#ifdef DEBUG
        WriteDataFile("awaited1", cerum::globals::enc1_ref.data(), cerum::globals::enc1_ref.size());
        WriteDataFile("real1", outputVector1.data(), outputVector1.size() * 4);
        WriteDataFile("awaited2", cerum::globals::enc2_ref.data(), cerum::globals::enc2_ref.size());
        WriteDataFile("real2", outputVector2.data(), outputVector2.size() * 4);
#endif
        if (outputVector1.size() != 0 && outputVector2.size() != 0
            && memcmp(outputVector1.data(), cerum::globals::enc1_ref.data(), outputVector1.size() * sizeof(int)) == CTOBF_INT32(0)
            && memcmp(outputVector2.data(), cerum::globals::enc2_ref.data(), outputVector2.size() * sizeof(int)) == CTOBF_INT32(0))
        {
          if (licCheckMode)
            savedLicense.write();
          SetActivationMode(true);
        }
      }
      licCheckMode = false;
      notesGathered = false;
      notes.clear();
    });
    pGraphics->AttachControl(this->computer);

    SetActivationMode(false);
    CheckExistingLicense();
  };
#endif
}

Cerum::~Cerum()
{
  stopRequested = true;
#if IPLUG_DSP
  if (activationThread.joinable())
    activationThread.join();
#endif
}

#ifdef DEBUG
void Cerum::LogToUI(const std::string& message)
{
  if (!GetUI())
    return;

  mLogMessages.push_back(message);
  if (mLogMessages.size() > 10)
    mLogMessages.pop_front();

  std::string logText = "";
  for (const auto& msg : mLogMessages)
    logText += msg + "\n";

  auto* logControl = dynamic_cast<ITextControl*>(GetUI()->GetControlWithTag(logDisplay));
  if (logControl)
  {
    logControl->SetStr(logText.c_str());
    GetUI()->SetAllControlsDirty();
  }
}
#endif

#if IPLUG_DSP
void Cerum::ProcessBlock(sample** inputs, sample** outputs, int nFrames)
{
  mDSP.ProcessBlock(nullptr, outputs, 2, nFrames, mTimeInfo.mPPQPos, mTimeInfo.mTransportIsRunning);
  mMeterSender.ProcessBlock(outputs, nFrames, meterControl, 2);
}

void Cerum::OnIdle() { mMeterSender.TransmitData(*this); }

void Cerum::OnReset()
{
  mDSP.Reset(GetSampleRate(), GetBlockSize());
  mMeterSender.Reset(GetSampleRate());
  for (int paramIdx = 0; paramIdx < kNumParams; ++paramIdx)
    mDSP.SetParam(paramIdx, GetParam(paramIdx)->Value());
}

void Cerum::ProcessMidiMsg(const IMidiMsg& msg)
{
  TRACE;

  int status = msg.StatusMsg();
  int noteId = msg.NoteNumber();

  if (!pluginActivated)
  {
    switch (status)
    {
    case IMidiMsg::kNoteOn:
      noteStartTimes[noteId] = mTimeInfo.mPPQPos * CTOBF_INT32(100);
      break;
    case IMidiMsg::kNoteOff:
      Note note = Note();

      note.noteId = noteId;
      note.startTime = noteStartTimes[noteId];
      note.duration = (unsigned long long)(mTimeInfo.mPPQPos * CTOBF_INT32(100) - noteStartTimes[noteId]);

      if (note.duration == CTOBF_INT32(1) && note.noteId == CTOBF_INT32(0))
        licStartSeqPrevNote = 0;

      if (note.duration == CTOBF_INT32(1) && licStartSeqPrevNote == noteId - CTOBF_INT32(1))
      {
        licStartSeqPrevNote = noteId;
        licStartCount++;
      }
      else
        licStartCount = 0;

      if (licStartCount == CTOBF_INT32(127) && note.noteId == CTOBF_INT32(127) && !licCheckMode)
      {
#ifdef DEBUG
        LogToUI("Got license start sequence");
#endif // DEBUG

        notes.clear();
        notesGathered = false;
        licCheckMode = true;

        mDSP.ProcessMidiMsg(msg);

        StartActivationThread();
      }
      else if (licCheckMode && !notesGathered)
      {
        notes.push_back(note);

#ifdef DEBUG
        char buffer[100];
        snprintf(buffer, 100, "%zd notes", notes.size());
        LogToUI(buffer);
        if (notes.size() == 1015)
        {
          std::sort(notes.begin(), notes.end(), [](Note a, Note b) {
            if (a.startTime != b.startTime)
              return a.startTime < b.startTime;
            if (a.duration != b.duration)
              return a.duration < b.duration;
            return a.noteId < b.noteId;
          });
          WriteDataFile("notes.dump", notes.data(), notes.size() * sizeof(Note));
        }
#endif // DEBUG
      }
      break;
    }
  }

  switch (status)
  {
  case IMidiMsg::kNoteOn:
  case IMidiMsg::kNoteOff:
    if (!licCheckMode)
      mDSP.ProcessMidiMsg(msg);
    break;
  }
}

void Cerum::OnParamChange(int paramIdx) { mDSP.SetParam(paramIdx, GetParam(paramIdx)->Value()); }

bool Cerum::OnMessage(int msgTag, int ctrlTag, int dataSize, const void* pData) { return false; }

void Cerum::SetActivationMode(bool isLicensed)
{
  if (!GetUI())
    return;

  const std::array<int, 13> gatedControls{
    osc2GainControl,
    osc2WaveControl,
    osc2OctaveControl,
    osc2DetuneControl,
    osc2PanControl,
    osc3GainControl,
    osc3WaveControl,
    osc3OctaveControl,
    osc3DetuneControl,
    osc3PanControl,
    masterGain,
    driveGain,
    limiterCeilingControl
  };

  const std::array<int, 4> gatedEnvelopeControls{
    attackControl,
    decayControl,
    sustainControl,
    releaseControl
  };

  pluginActivated = isLicensed;

  for (const auto tag : gatedControls)
    GetUI()->GetControlWithTag(tag)->SetDisabled(!isLicensed);

  for (const auto tag : gatedEnvelopeControls)
    GetUI()->GetControlWithTag(tag)->SetDisabled(!isLicensed);

  const char* lic = OBF("LICENSED");
  const char* trial = OBF("TRIAL MODE");

  GetUI()->GetControlWithTag(modeDisplayText)->As<ITextControl>()->SetStr(isLicensed ? lic : trial);
  GetUI()->SetAllControlsDirty();
}

void Cerum::CheckExistingLicense()
{
  if (savedLicense.exists())
  {
    savedLicense.read();
    notes = savedLicense.notes;
    StartLicenseCheck(notes.size());
  }
}

void Cerum::OnHostIdentified()
{
  using namespace cerum::globals;

  if (!loaded)
  {
    auto ptr = HiddenPtr<lic::ClientConfig>(&licClientConfig).get();

    ptr->host = OBF("cerumvst.com");
    ptr->port = CTOBF_INT32(44330);
    ptr->shared_secret = (HiddenPtr<char>(sharedSecret).get());
    ptr->server_name = OBF("cerumvst-srv");
    ptr->ca_cert_pem = (HiddenPtr<char>(ca_cert).get());
    ptr->client_cert_pem = (HiddenPtr<char>(client_tls_cert).get());
    ptr->client_key_pem = (HiddenPtr<char>(client_tls_key).get());

    cerum::PostStartup();

    loaded = 1;
  }
}

void Cerum::StartActivationThread()
{
  bool expected = false;
  if (!activationInProgress.compare_exchange_strong(expected, true))
    return;

  if (activationThread.joinable())
    activationThread.join();

  activationThread = std::thread([this]() {
    try
    {
      (this->*ActivationMethod)();
    }
    catch (...)
    {
      MessageBoxA(NULL, OBF("Error!"), AY_OBFUSCATE("cerum"), MB_ICONERROR | MB_OK);
    }

    activationInProgress = false;
  });
}

void Cerum::Activate()
{
  printf("[DEBUG] check started");

  while (notes.size() < CTOBF_INT32(626))
    Sleep(1);
  notesGathered = true;

  bool licensed = memcmp(cerum::globals::enc1_ref.data(), notes.data(), cerum::globals::enc1_ref.size()) == 0;

  SetActivationMode(licensed);
}

void Cerum::RealActivate()
{
  lic::ActivationResponse resp;
  if (!licrefDownloaded)
  {
    WDL_String host;
    this->GetRawHostStr(host);

    lic::LicenseClient licClient(cerum::globals::licClientConfig);

    lic::ActivationRequest activationRequest;
    activationRequest.vst_host = host.Get();
    activationRequest.hwid = hwid::get();
    activationRequest.license_key = AY_OBFUSCATE("cerum");

    licClient.connect();
    resp = licClient.activate(activationRequest);
    licClient.close();

    cerum::globals::enc1_ref.clear();
    cerum::globals::enc2_ref.clear();

    cerum::InflateBuffer((char*)resp.rhs1_gzip.data(), resp.rhs1_gzip.size(), cerum::globals::enc1_ref);
    cerum::InflateBuffer((char*)resp.rhs2_gzip.data(), resp.rhs2_gzip.size(), cerum::globals::enc2_ref);

    cerum::globals::notesCount = resp.sys_size;

    savedLicense.checker = resp.offline_check;
    savedLicense.signature = resp.signature;

    licrefDownloaded = true;
  }

  while (!stopRequested && notes.size() < cerum::globals::notesCount)
    Sleep(1);
  notesGathered = true;

  notes.resize(cerum::globals::notesCount);

  std::sort(notes.begin(), notes.end(), [](Note a, Note b) {
    if (a.startTime != b.startTime)
      return a.startTime < b.startTime;
    if (a.duration != b.duration)
      return a.duration < b.duration;
    return a.noteId < b.noteId;
  });

  savedLicense.notes = notes;

  StartLicenseCheck(cerum::globals::notesCount);
}

void Cerum::StartLicenseCheck(int notesCount)
{
  std::vector<Scrambled> scrambledData(CTOBF_INT32(notesCount));
  memset(scrambledData.data(), 0, CTOBF_INT32(notesCount) * sizeof(Scrambled));

  scramble_xtea(notes, scrambledData);

  computer->PublishData(scrambledData.data(), CTOBF_INT32(notesCount));
  computer->SetDirty(false);
}

#endif
