#pragma once

#include <algorithm>
#include <array>
#include <cmath>

#include "globals.h"
#include "MidiSynth.h"
#include "ADSREnvelope.h"

using namespace iplug;

template <typename T>
class CerumDSP
{
public:
  static constexpr int kNumOscillators = 3;

  enum EWaveform
  {
    kWaveSine = 0,
    kWaveTriangle,
    kWaveSaw,
    kWaveSquare,
    kNumWaveforms
  };

  struct OscillatorSettings
  {
    double gain = 0.0;
    int wave = kWaveSine;
    int octave = 0;
    double detuneCents = 0.0;
    double pan = 0.0;
  };

  class Oscillator
  {
  public:
    void SetSampleRate(double sampleRate)
    {
      mSampleRate = sampleRate;
    }

    void Reset()
    {
      mPhase = 0.0;
    }

    T Process(double frequency, int wave)
    {
      if (mSampleRate <= 0.0)
        return 0.0;

      const double phaseInc = frequency / mSampleRate;
      const double phase = mPhase;
      T value = 0.0;

      switch (wave)
      {
      case kWaveTriangle:
        value = static_cast<T>(4.0 * std::fabs(phase - 0.5) - 1.0);
        break;
      case kWaveSaw:
        value = static_cast<T>((2.0 * phase) - 1.0);
        break;
      case kWaveSquare:
        value = phase < 0.5 ? static_cast<T>(1.0) : static_cast<T>(-1.0);
        break;
      case kWaveSine:
      default:
        value = static_cast<T>(std::sin(phase * 2.0 * PI));
        break;
      }

      mPhase += phaseInc;
      if (mPhase >= 1.0)
        mPhase -= std::floor(mPhase);

      return value;
    }

  private:
    double mSampleRate = 44100.0;
    double mPhase = 0.0;
  };

public:
  class Voice : public SynthVoice
  {
  public:
    explicit Voice(CerumDSP<T>* parent)
      : mAmpEnv("amp", [this]() { ResetOscillators(); })
      , mParentPlugin(parent)
    {
    }

    bool GetBusy() const override
    {
      return mAmpEnv.GetBusy();
    }

    void Trigger(double level, bool isRetrigger) override
    {
      ResetOscillators();

      if (isRetrigger)
        mAmpEnv.Retrigger(level);
      else
        mAmpEnv.Start(level);
    }

    void Release() override
    {
      mAmpEnv.Release();
    }

    void ProcessSamplesAccumulating(sample** inputs, sample** outputs, int nInputs, int nOutputs, int startIdx, int nFrames) override
    {
      const double pitch = mInputs[kVoiceControlPitch].endValue + mInputs[kVoiceControlPitchBend].endValue;
      const double baseFrequency = 440.0 * std::pow(2.0, pitch);

      for (auto i = startIdx; i < startIdx + nFrames; ++i)
      {
        const T env = mAmpEnv.Process(static_cast<T>(mParentPlugin->mSustain));
        T left = 0.0;
        T right = 0.0;

        for (int oscIdx = 0; oscIdx < kNumOscillators; ++oscIdx)
        {
          const auto& settings = mParentPlugin->mOscillators[oscIdx];
          if (settings.gain <= 0.0)
            continue;

          const double octaveRatio = std::pow(2.0, static_cast<double>(settings.octave));
          const double detuneRatio = std::pow(2.0, settings.detuneCents / 1200.0);
          const double frequency = baseFrequency * octaveRatio * detuneRatio;
          const T oscSample = mOscillators[oscIdx].Process(frequency, settings.wave) * static_cast<T>(settings.gain);
          const T pan = static_cast<T>(settings.pan);
          const T leftPan = static_cast<T>(0.5 * (1.0 - pan));
          const T rightPan = static_cast<T>(0.5 * (1.0 + pan));

          left += oscSample * leftPan;
          right += oscSample * rightPan;
        }

        outputs[0][i] += left * env;
        if (nOutputs > 1)
          outputs[1][i] += right * env;
      }
    }

    void SetSampleRateAndBlockSize(double sampleRate, int blockSize) override
    {
      for (auto& oscillator : mOscillators)
        oscillator.SetSampleRate(sampleRate);

      mAmpEnv.SetSampleRate(sampleRate);
      mAmpEnv.SetStageTime(ADSREnvelope<T>::kAttack, mParentPlugin->mAttackMs);
      mAmpEnv.SetStageTime(ADSREnvelope<T>::kDecay, mParentPlugin->mDecayMs);
      mAmpEnv.SetStageTime(ADSREnvelope<T>::kRelease, mParentPlugin->mReleaseMs);
    }

    ADSREnvelope<T> mAmpEnv;

  private:
    void ResetOscillators()
    {
      for (auto& oscillator : mOscillators)
        oscillator.Reset();
    }

    std::array<Oscillator, kNumOscillators> mOscillators;
    CerumDSP<T>* mParentPlugin = nullptr;
  };

public:
  explicit CerumDSP(int nVoices)
  {
    mOscillators[0].gain = 0.8;
    mOscillators[0].wave = kWaveSine;
    mOscillators[0].octave = 0;
    mOscillators[0].detuneCents = 0.0;
    mOscillators[0].pan = 0.0;

    mOscillators[1].gain = 0.35;
    mOscillators[1].wave = kWaveSaw;
    mOscillators[1].octave = 1;
    mOscillators[1].detuneCents = 7.0;
    mOscillators[1].pan = -0.35;

    mOscillators[2].gain = 0.25;
    mOscillators[2].wave = kWaveSquare;
    mOscillators[2].octave = -1;
    mOscillators[2].detuneCents = -7.0;
    mOscillators[2].pan = 0.35;

    for (int i = 0; i < nVoices; ++i)
      mSynth.AddVoice(new Voice(this), 0);
  }

  void ProcessBlock(T** inputs, T** outputs, int nOutputs, int nFrames, double qnPos = 0., bool transportIsRunning = false, double tempo = 120.)
  {
    for (int channel = 0; channel < nOutputs; ++channel)
      memset(outputs[channel], 0, nFrames * sizeof(T));

    mSynth.ProcessBlock(inputs, outputs, 0, nOutputs, nFrames);

    const T driveAmount = static_cast<T>(1.0 + (mDrive * 8.0));
    const T driveNorm = static_cast<T>(1.0 / std::tanh(driveAmount));

    for (int sampleIdx = 0; sampleIdx < nFrames; ++sampleIdx)
    {
      T left = outputs[0][sampleIdx];
      T right = nOutputs > 1 ? outputs[1][sampleIdx] : left;

      left = std::tanh(left * driveAmount) * driveNorm;
      right = std::tanh(right * driveAmount) * driveNorm;

      left *= static_cast<T>(mMasterGain);
      right *= static_cast<T>(mMasterGain);

      const T peak = std::max(std::fabs(left), std::fabs(right));
      T targetGain = 1.0;
      if (peak > static_cast<T>(mLimiterCeiling) && peak > 0.0)
        targetGain = static_cast<T>(mLimiterCeiling) / peak;

      if (targetGain < mLimiterGain)
        mLimiterGain = targetGain;
      else
        mLimiterGain += (targetGain - mLimiterGain) * static_cast<T>(1.0 - mLimiterReleaseCoeff);

      outputs[0][sampleIdx] = left * mLimiterGain;
      if (nOutputs > 1)
        outputs[1][sampleIdx] = right * mLimiterGain;
    }
  }

  void Reset(double sampleRate, int blockSize)
  {
    mSampleRate = sampleRate;
    mSynth.SetSampleRateAndBlockSize(sampleRate, blockSize);
    mSynth.Reset();
    mLimiterGain = 1.0;
    mLimiterReleaseCoeff = std::exp(-1.0 / (sampleRate * 0.05));
    ApplyEnvelopeSettings();
  }

  void ProcessMidiMsg(const IMidiMsg& msg)
  {
    mSynth.AddMidiMsgToQueue(msg);
  }

  void SetParam(int paramIdx, double value)
  {
    switch (paramIdx)
    {
    case kParamMaster:
      mMasterGain = value;
      break;
    case kParamDrive:
      mDrive = value;
      break;
    case kParamLimiterCeiling:
      mLimiterCeiling = value;
      break;
    case kParamAttack:
      mAttackMs = value;
      ApplyEnvelopeStage(ADSREnvelope<T>::kAttack, value);
      break;
    case kParamDecay:
      mDecayMs = value;
      ApplyEnvelopeStage(ADSREnvelope<T>::kDecay, value);
      break;
    case kParamSustain:
      mSustain = value / 100.0;
      break;
    case kParamRelease:
      mReleaseMs = value;
      ApplyEnvelopeStage(ADSREnvelope<T>::kRelease, value);
      break;
    case kParamOsc1Gain:
    case kParamOsc1Wave:
    case kParamOsc1Octave:
    case kParamOsc1Detune:
    case kParamOsc1Pan:
    case kParamOsc2Gain:
    case kParamOsc2Wave:
    case kParamOsc2Octave:
    case kParamOsc2Detune:
    case kParamOsc2Pan:
    case kParamOsc3Gain:
    case kParamOsc3Wave:
    case kParamOsc3Octave:
    case kParamOsc3Detune:
    case kParamOsc3Pan:
      SetOscillatorParam(paramIdx, value);
      break;
    case kParamGlideTime:
      mSynth.SetNoteGlideTime(value / 1000.0);
      break;
    default:
      break;
    }
  }

  void ApplyEnvelopeSettings()
  {
    ApplyEnvelopeStage(ADSREnvelope<T>::kAttack, mAttackMs);
    ApplyEnvelopeStage(ADSREnvelope<T>::kDecay, mDecayMs);
    ApplyEnvelopeStage(ADSREnvelope<T>::kRelease, mReleaseMs);
  }

private:
  void ApplyEnvelopeStage(int stage, double value)
  {
    mSynth.ForEachVoice([stage, value](SynthVoice& voice) {
      dynamic_cast<Voice&>(voice).mAmpEnv.SetStageTime(stage, value);
    });
  }

  void SetOscillatorParam(int paramIdx, double value)
  {
    const int oscIdx = (paramIdx - kParamOsc1Gain) / 5;
    const int oscParam = (paramIdx - kParamOsc1Gain) % 5;
    auto& osc = mOscillators[oscIdx];

    switch (oscParam)
    {
    case 0:
      osc.gain = value;
      break;
    case 1:
      osc.wave = static_cast<int>(value);
      break;
    case 2:
      osc.octave = static_cast<int>(value);
      break;
    case 3:
      osc.detuneCents = value;
      break;
    case 4:
      osc.pan = value / 100.0;
      break;
    default:
      break;
    }
  }

public:
  double mMasterGain = 0.8;
  double mDrive = 0.15;
  double mLimiterCeiling = 0.95;
  double mAttackMs = 10.0;
  double mDecayMs = 140.0;
  double mSustain = 0.75;
  double mReleaseMs = 280.0;
  std::array<OscillatorSettings, kNumOscillators> mOscillators;
  MidiSynth mSynth{VoiceAllocator::kPolyModePoly, MidiSynth::kDefaultBlockSize};

private:
  double mSampleRate = DEFAULT_SAMPLE_RATE;
  T mLimiterGain = 1.0;
  double mLimiterReleaseCoeff = 0.0;
};
