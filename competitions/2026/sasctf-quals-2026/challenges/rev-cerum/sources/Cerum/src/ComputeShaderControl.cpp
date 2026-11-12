#include "ComputeShaderControl.h"

#include <algorithm>
#include <memory>
#include <utility>

BEGIN_IPLUG_NAMESPACE
BEGIN_IGRAPHICS_NAMESPACE

LicenseCheckerControl::LicenseCheckerControl(const IRECT& bounds, std::function<void(LicenseCheckerControl*)> computeCompletedHandler)
  : IControl(bounds)
  , computeCompletedHandler(std::move(computeCompletedHandler))
{
}

LicenseCheckerControl::~LicenseCheckerControl()
{
  DestroyGLObjects();
}

void LicenseCheckerControl::PublishData(const Scrambled* notes, std::size_t count) noexcept
{
  if (notes == nullptr)
    return;

  if (mPublishedCount.load(std::memory_order_acquire) != count)
    ResizeNoteStorage(count);

  mInputSeq.fetch_add(1u, std::memory_order_acq_rel);

  for (std::size_t i = 0; i < count; ++i)
  {
    GpuNote n = {};
    n.xoredTime = notes[i].xoredTime;
    n.enc1 = notes[i].enc1;
    n.enc2 = notes[i].enc2;

    mInputRtNotes[i].xoredTime.store(n.xoredTime, std::memory_order_relaxed);
    mInputRtNotes[i].enc1.store(n.enc1, std::memory_order_relaxed);
    mInputRtNotes[i].enc2.store(n.enc2, std::memory_order_relaxed);
  }

  dataLoaded.store(true);
  mInputSeq.fetch_add(1u, std::memory_order_release);
}

bool LicenseCheckerControl::CopyLastGpuResult(int32_t* outputVector1, int32_t* outputVector2, std::size_t count) const noexcept
{
  if (outputVector1 == nullptr || outputVector2 == nullptr)
    return false;

  const std::size_t publishedCount = mPublishedCount.load(std::memory_order_acquire);
  const std::size_t copyCount = std::min(count, publishedCount);

  for (int attempt = 0; attempt < 4; ++attempt)
  {
    const std::uint32_t s0 = mOutputSeq.load(std::memory_order_acquire);
    if ((s0 & 1u) != 0u)
      continue;

    std::vector<std::uint32_t> local1(copyCount);
    std::vector<std::uint32_t> local2(copyCount);

    for (std::size_t i = 0; i < copyCount; ++i)
    {
      local1[i] = mShaderOutput1[i].load(std::memory_order_relaxed);
      local2[i] = mShaderOutput2[i].load(std::memory_order_relaxed);
    }

    std::atomic_thread_fence(std::memory_order_acquire);

    const std::uint32_t s1 = mOutputSeq.load(std::memory_order_acquire);
    if (s0 == s1 && (s1 & 1u) == 0u)
    {
      for (std::size_t i = 0; i < copyCount; ++i)
      {
        outputVector1[i] = static_cast<int32_t>(local1[i]);
        outputVector2[i] = static_cast<int32_t>(local2[i]);
      }

      return true;
    }
  }

  return false;
}

void LicenseCheckerControl::Draw(IGraphics& g)
{
  IGraphics::ScopedGLContext scopedGLContext(&g);

  if (dataLoaded)
  {
    if (!EnsureGLObjects())
      return;

    RunCompute();
    computeCompletedHandler(this);
    dataLoaded.store(false);
  }
}

void LicenseCheckerControl::OnResize()
{
}

bool LicenseCheckerControl::PullLatestAudioNotesForGpu() noexcept
{
  const std::size_t count = mPublishedCount.load(std::memory_order_acquire);

  for (int attempt = 0; attempt < 4; ++attempt)
  {
    const std::uint32_t s0 = mInputSeq.load(std::memory_order_acquire);
    if ((s0 & 1u) != 0u)
      continue;

    std::vector<GpuNote> local(count);
    for (std::size_t i = 0; i < count; ++i)
    {
      local[i].xoredTime = mInputRtNotes[i].xoredTime.load(std::memory_order_relaxed);
      local[i].enc1 = mInputRtNotes[i].enc1.load(std::memory_order_relaxed);
      local[i].enc2 = mInputRtNotes[i].enc2.load(std::memory_order_relaxed);
    }

    std::atomic_thread_fence(std::memory_order_acquire);

    const std::uint32_t s1 = mInputSeq.load(std::memory_order_acquire);
    if (s0 == s1 && (s1 & 1u) == 0u)
    {
      mGpuInputNotes = std::move(local);
      return true;
    }
  }

  return false;
}

void LicenseCheckerControl::PublishGpuResultToCpu()
{
  mOutputSeq.fetch_add(1u, std::memory_order_acq_rel);

  const std::size_t count = mPublishedCount.load(std::memory_order_acquire);
  for (std::size_t i = 0; i < count; ++i)
  {
    mShaderOutput1[i].store(mGpuOutput1[i], std::memory_order_relaxed);
    mShaderOutput2[i].store(mGpuOutput2[i], std::memory_order_relaxed);
  }

  mOutputSeq.fetch_add(1u, std::memory_order_release);
}

GLuint LicenseCheckerControl::CompileShader(GLenum type, const char* source)
{
  const GLuint shader = glCreateShader(type);
  glShaderSource(shader, 1, &source, nullptr);
  glCompileShader(shader);

  GLint ok = GL_FALSE;
  glGetShaderiv(shader, GL_COMPILE_STATUS, &ok);
  return ok == GL_TRUE ? shader : 0;
}

GLuint LicenseCheckerControl::LinkProgram(GLuint computeShader)
{
  const GLuint program = glCreateProgram();
  glAttachShader(program, computeShader);
  glLinkProgram(program);

  GLint ok = GL_FALSE;
  glGetProgramiv(program, GL_LINK_STATUS, &ok);
  return ok == GL_TRUE ? program : 0;
}

bool LicenseCheckerControl::EnsureGLObjects()
{
  using namespace cerum::globals;

  const std::size_t count = mPublishedCount.load(std::memory_order_acquire);

  if (mProgram == 0)
  {
    const GLuint cs = CompileShader(GL_COMPUTE_SHADER, kComputeShader);
    if (cs == 0)
      return false;

    mProgram = LinkProgram(cs);
    glDeleteShader(cs);

    if (mProgram == 0)
      return false;
  }

  bool ok = true;
  ok &= CreateSSBO(&mInputVectorSSBO, mGpuInputNotes.data(), sizeof(GpuNote) * count, GL_DYNAMIC_DRAW);
  ok &= CreateSSBO(&mOutputVector1SSBO, nullptr, count * 4, GL_DYNAMIC_READ);
  ok &= CreateSSBO(&mOutputVector2SSBO, nullptr, count * 4, GL_DYNAMIC_READ);
  ok &= CreateSSBO(&mMatrix1SSBO, enc1_matrix.data(), enc1_matrix.size(), GL_DYNAMIC_READ);
  ok &= CreateSSBO(&mMatrix2SSBO, enc2_matrix.data(), enc2_matrix.size(), GL_DYNAMIC_READ);
  return ok;
}

bool LicenseCheckerControl::CreateSSBO(GLuint* ssboPtr, const void* data, GLsizeiptr size, GLenum usage)
{
  if (*ssboPtr == 0)
    glGenBuffers(1, ssboPtr);

  glBindBuffer(GL_SHADER_STORAGE_BUFFER, *ssboPtr);
  glBufferData(GL_SHADER_STORAGE_BUFFER, size, data, usage);
  glBindBuffer(GL_SHADER_STORAGE_BUFFER, 0);

  return *ssboPtr != 0;
}

void LicenseCheckerControl::RunCompute()
{
  PullLatestAudioNotesForGpu();

  const std::size_t count = mPublishedCount.load(std::memory_order_acquire);
  if (count == 0)
    return;

  glBindBuffer(GL_SHADER_STORAGE_BUFFER, mInputVectorSSBO);
  glBufferSubData(GL_SHADER_STORAGE_BUFFER, 0, static_cast<GLsizeiptr>(sizeof(GpuNote) * count), mGpuInputNotes.data());
  glBindBuffer(GL_SHADER_STORAGE_BUFFER, 0);

  glUseProgram(mProgram);
  glUniform1ui(7, static_cast<GLuint>(count));
  glUniform1ui(8, static_cast<GLuint>(*(HiddenPtr<int>(&cerum::globals::hwidSeed).get())));

  glBindBufferBase(GL_SHADER_STORAGE_BUFFER, 1, mInputVectorSSBO);
  glBindBufferBase(GL_SHADER_STORAGE_BUFFER, 2, mOutputVector1SSBO);
  glBindBufferBase(GL_SHADER_STORAGE_BUFFER, 3, mOutputVector2SSBO);
  glBindBufferBase(GL_SHADER_STORAGE_BUFFER, 4, mMatrix1SSBO);
  glBindBufferBase(GL_SHADER_STORAGE_BUFFER, 5, mMatrix2SSBO);

  constexpr GLuint localSizeX = 256u;
  const GLuint groupsX = static_cast<GLuint>((count + localSizeX - 1u) / localSizeX);
  glDispatchCompute(groupsX, 1u, 1u);

  glMemoryBarrier(GL_SHADER_STORAGE_BARRIER_BIT | GL_BUFFER_UPDATE_BARRIER_BIT);

  glBindBuffer(GL_SHADER_STORAGE_BUFFER, mOutputVector1SSBO);
  glGetBufferSubData(GL_SHADER_STORAGE_BUFFER, 0, static_cast<GLsizeiptr>(sizeof(int32_t) * count), mGpuOutput1.data());
  glBindBuffer(GL_SHADER_STORAGE_BUFFER, 0);

  glBindBuffer(GL_SHADER_STORAGE_BUFFER, mOutputVector2SSBO);
  glGetBufferSubData(GL_SHADER_STORAGE_BUFFER, 0, static_cast<GLsizeiptr>(sizeof(int32_t) * count), mGpuOutput2.data());
  glBindBuffer(GL_SHADER_STORAGE_BUFFER, 0);

  PublishGpuResultToCpu();

  glBindBufferBase(GL_SHADER_STORAGE_BUFFER, 1, 0);
  glBindBufferBase(GL_SHADER_STORAGE_BUFFER, 2, 0);
  glBindBufferBase(GL_SHADER_STORAGE_BUFFER, 3, 0);
  glBindBufferBase(GL_SHADER_STORAGE_BUFFER, 4, 0);
  glBindBufferBase(GL_SHADER_STORAGE_BUFFER, 5, 0);
  glUseProgram(0);
}

void LicenseCheckerControl::DestroyGLObjects()
{
  if (mProgram != 0)
  {
    glDeleteProgram(mProgram);
    mProgram = 0;
  }

  DeleteSSBO(&mInputVectorSSBO);
  DeleteSSBO(&mOutputVector1SSBO);
  DeleteSSBO(&mOutputVector2SSBO);
  DeleteSSBO(&mMatrix1SSBO);
  DeleteSSBO(&mMatrix2SSBO);
}

void LicenseCheckerControl::DeleteSSBO(GLuint* ssboPtr)
{
  if (*ssboPtr != 0)
  {
    glDeleteBuffers(1, ssboPtr);
    *ssboPtr = 0;
  }
}

void LicenseCheckerControl::ResizeNoteStorage(std::size_t count)
{
  mInputSeq.fetch_add(1u, std::memory_order_acq_rel);
  mOutputSeq.fetch_add(1u, std::memory_order_acq_rel);

  mGpuInputNotes.assign(count, {});
  mGpuOutput1.assign(count, 0u);
  mGpuOutput2.assign(count, 0u);

  mInputRtNotes = std::vector<RtAtomicNote>(count);
  mShaderOutput1 = std::vector<std::atomic<std::uint32_t>>(count);
  mShaderOutput2 = std::vector<std::atomic<std::uint32_t>>(count);

  mPublishedCount.store(count, std::memory_order_release);

  mOutputSeq.fetch_add(1u, std::memory_order_release);
  mInputSeq.fetch_add(1u, std::memory_order_release);
}

END_IGRAPHICS_NAMESPACE
END_IPLUG_NAMESPACE
