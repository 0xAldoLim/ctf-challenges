#pragma once

#include <atomic>
#include <cstddef>
#include <cstdint>
#include <functional>
#include <vector>

#include <glad/glad.h>

#include "IControl.h"
#include "IGraphics.h"
#include "Note.h"
#include "globals.h"
#include "ptr_obfuscate.h"

BEGIN_IPLUG_NAMESPACE
BEGIN_IGRAPHICS_NAMESPACE

class LicenseCheckerControl final : public IControl
{
public:
  explicit LicenseCheckerControl(const IRECT& bounds, std::function<void(LicenseCheckerControl*)> computeCompletedHandler);
  ~LicenseCheckerControl() override;

  void PublishData(const Scrambled* notes, std::size_t count) noexcept;
  bool CopyLastGpuResult(int32_t* outputVector1, int32_t* outputVector2, std::size_t count) const noexcept;

  void Draw(IGraphics& g) override;
  void OnResize() override;

private:
  struct alignas(4) GpuNote
  {
    std::uint32_t xoredTime = 0;
    std::uint32_t enc1 = 0;
    std::uint32_t enc2 = 0;
  };

  struct RtAtomicNote
  {
    std::atomic<std::uint32_t> xoredTime{0};
    std::atomic<std::uint32_t> enc1{0};
    std::atomic<std::uint32_t> enc2{0};
  };

  bool PullLatestAudioNotesForGpu() noexcept;
  void PublishGpuResultToCpu();
  static GLuint CompileShader(GLenum type, const char* source);
  static GLuint LinkProgram(GLuint computeShader);
  bool EnsureGLObjects();
  bool CreateSSBO(GLuint* ssboPtr, const void* data, GLsizeiptr size, GLenum usage);
  void RunCompute();
  void DestroyGLObjects();
  void DeleteSSBO(GLuint* ssboPtr);
  void ResizeNoteStorage(std::size_t count);

private:
  GLuint mProgram = 0;

  GLuint mInputVectorSSBO = 0;
  GLuint mMatrix1SSBO = 0;
  GLuint mMatrix2SSBO = 0;
  GLuint mOutputVector1SSBO = 0;
  GLuint mOutputVector2SSBO = 0;

  std::vector<GpuNote> mGpuInputNotes;
  std::vector<std::uint32_t> mGpuOutput1;
  std::vector<std::uint32_t> mGpuOutput2;

  std::vector<RtAtomicNote> mInputRtNotes;
  std::vector<std::atomic<std::uint32_t>> mShaderOutput1;
  std::vector<std::atomic<std::uint32_t>> mShaderOutput2;

  std::atomic<std::uint32_t> mInputSeq{0};
  std::atomic<std::uint32_t> mOutputSeq{0};
  std::atomic<std::size_t> mPublishedCount{0};
  std::atomic<bool> dataLoaded{0};

  std::function<void(LicenseCheckerControl*)> computeCompletedHandler;
};

END_IGRAPHICS_NAMESPACE
END_IPLUG_NAMESPACE
