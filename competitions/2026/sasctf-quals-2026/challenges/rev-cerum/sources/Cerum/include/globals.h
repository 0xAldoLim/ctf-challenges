#pragma once

#include <cstdint>
#include <vector>

#include "licensing_client.hpp"

#define PLUGIN_DATA_DIR "cerum"
#define LIC_FILENAME "cerum.dat"

namespace cerum::globals
{
extern const char* anti_ai1;
extern const char* anti_ai2;

extern int hwidSeed;

extern std::vector<char> enc1_matrix;
extern std::vector<char> enc2_matrix;
extern std::vector<char> enc1_ref;
extern std::vector<char> enc2_ref;

extern char xor_key1;
extern char xor_key2;

extern unsigned int notesCount;

extern char shaderModifier[];
extern const int shaderModifierSize;
extern char kComputeShader[];
extern char shaderKey[];

extern char* client_tls_cert;
extern char* client_tls_key;
extern char* ca_cert;
extern char* lic_key;
extern char* sharedSecret;

extern lic::ClientConfig licClientConfig;
} // namespace cerum::globals

enum EParams
{
  kParamMaster = 0,
  kParamDrive,
  kParamLimiterCeiling,
  kParamAttack,
  kParamDecay,
  kParamSustain,
  kParamRelease,
  kParamOsc1Gain,
  kParamOsc1Wave,
  kParamOsc1Octave,
  kParamOsc1Detune,
  kParamOsc1Pan,
  kParamOsc2Gain,
  kParamOsc2Wave,
  kParamOsc2Octave,
  kParamOsc2Detune,
  kParamOsc2Pan,
  kParamOsc3Gain,
  kParamOsc3Wave,
  kParamOsc3Octave,
  kParamOsc3Detune,
  kParamOsc3Pan,
  kParamGlideTime,
  kNumParams
};

enum EControlTags
{
  modeSwitchButton = 0,
  modeDisplayText,
  keyboardControl,
  meterControl,
  logDisplay,
  debugBtn,
  osc1GainControl,
  osc1WaveControl,
  osc1OctaveControl,
  osc1DetuneControl,
  osc1PanControl,
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
  attackControl,
  decayControl,
  sustainControl,
  releaseControl,
  masterGain,
  driveGain,
  limiterCeilingControl,
  glideTimeControl
};
