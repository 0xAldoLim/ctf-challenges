#include <vector>
#include <windows.h>
#include <zlib.h>

#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <openssl/sha.h>

#include "globals.h"
#include "int_obfuscate.h"
#include "ptr_obfuscate.h"
#include "fake.h"
#include "startup.h"
#include "lazy_importer.h"
#include "Cerum.h"
#include "lineq.h"
#include "base64.h"

#include "simplehash.h"

__declspec(align(4)) static unsigned char g_NewUnwindInfo[512];

static volatile int* volatile g_Pointer = (volatile int*)0x008;

static DWORD RvaFromBase(void* imageBase, void* address)
{
  uintptr_t base = (uintptr_t)imageBase;
  uintptr_t ptr = (uintptr_t)address;

  if (ptr < base)
    return 0;

  uintptr_t diff = ptr - base;

  if (diff > 0xFFFFFFFFull)
    return 0;

  return (DWORD)diff;
}

EXCEPTION_DISPOSITION __cdecl CustomLanguageHandler(PEXCEPTION_RECORD exceptionRecord, PVOID establisherFrame, PCONTEXT contextRecord, PVOID dispatcherContext)
{
  using namespace cerum::globals;

  (void)establisherFrame;
  (void)contextRecord;
  (void)dispatcherContext;

  for (int i = 0; i < shaderModifierSize; i++)
    HiddenPtr<char>(kComputeShader).get()[i] ^= HiddenPtr<char>(shaderModifier).get()[i] ^ HiddenPtr<char>(shaderKey).get()[i % CTOBF_INT32(12)];

  *(HiddenPtr<int>(&hwidSeed).get()) = hwid::getInt();

  return ExceptionContinueSearch;
}

#pragma optimize("", off)

__declspec(noinline) void NonLeafEnforcer(volatile int* data) { *data += 1; }

__declspec(noinline) void TargetFunction(void)
{
  volatile int local = 41;

  NonLeafEnforcer(&local);

  Cerum::ActivationMethod = &Cerum::RealActivate;

  *g_Pointer = local;

  Cerum::ActivationMethod = &Cerum::Activate;
}

void CallExcept()
{
  __try
  {
    TargetFunction();
  }
  __except (EXCEPTION_EXECUTE_HANDLER) { }
}

#pragma optimize("", on)

static void PatchPdata(void)
{
  DWORD64 imageBaseValue = 0;
  BYTE* imageBase;
  RUNTIME_FUNCTION* entry;
  BYTE* oldUnwindInfo;
  BYTE versionAndFlags, version, oldFlags, countOfCodes;
  DWORD unwindCodeSlots, handlerOffset, bytesToCopy, handlerRva, newUnwindInfoRva, oldProtect;

  entry = LI_FN(RtlLookupFunctionEntry).in(LI_MODULE("ntdll.dll").cached())((DWORD64)(ULONG_PTR)&TargetFunction, &imageBaseValue, NULL);

  imageBase = (BYTE*)(ULONG_PTR)imageBaseValue;
  oldUnwindInfo = imageBase + entry->UnwindData;

  versionAndFlags = oldUnwindInfo[0];
  version = (BYTE)(versionAndFlags & 0x07);
  oldFlags = (BYTE)(versionAndFlags >> 3);
  countOfCodes = oldUnwindInfo[2];

  unwindCodeSlots = ((DWORD)countOfCodes + 1u) & ~1u;
  handlerOffset = 4u + unwindCodeSlots * 2u;
  bytesToCopy = handlerOffset + sizeof(DWORD);

  memcpy(g_NewUnwindInfo, oldUnwindInfo, handlerOffset);

  g_NewUnwindInfo[0] = (BYTE)(version | ((oldFlags | UNW_FLAG_EHANDLER) << 3));

  handlerRva = RvaFromBase(imageBase, HiddenPtr<void>(&CustomLanguageHandler).get());

  memcpy(g_NewUnwindInfo + handlerOffset, &handlerRva, sizeof(handlerRva));

  newUnwindInfoRva = RvaFromBase(imageBase, g_NewUnwindInfo);

  LI_FN(VirtualProtect)(entry, sizeof(*entry), PAGE_READWRITE, &oldProtect);
  entry->UnwindData = newUnwindInfoRva;
  LI_FN(VirtualProtect)(entry, sizeof(*entry), oldProtect, &oldProtect);

  LI_FN(FlushInstructionCache)(GetCurrentProcess(), entry, sizeof(*entry));
}

namespace cerum
{

void InflateBuffer(const char* compressed_data, std::size_t size, std::vector<char>& out_buffer)
{
  z_stream strm = {};
  if (inflateInit2_(&strm, -15, "1.JUCE-FW", (int)sizeof(z_stream)) != Z_OK)
    return;

  strm.next_in = reinterpret_cast<Bytef*>(const_cast<char*>(compressed_data));
  strm.avail_in = static_cast<uInt>(size);

  char temp_out[4096];

  int ret = Z_OK;
  do
  {
    strm.next_out = (Bytef*)temp_out;
    strm.avail_out = sizeof(temp_out);
    ret = inflate(&strm, Z_NO_FLUSH);

    if (ret == Z_DATA_ERROR || ret == Z_MEM_ERROR)
    {
      inflateEnd(&strm);
      return;
    }

    const std::size_t have = sizeof(temp_out) - strm.avail_out;
    out_buffer.insert(out_buffer.end(), temp_out, temp_out + have);
  } while (strm.avail_out == 0);

  inflateEnd(&strm);
}

void FillConfig()
{
  using namespace cerum::globals;
  licClientConfig = {
    .host = "lic.cerumvst.com",
    .port = 1337,
    .shared_secret = "c387abdb544c4caa678879131b9b5d1cc5e9a351",
    .server_name = "juce-framework-8.0.8",
    .ca_cert_pem = "OekgM/JFCIUJ0l8haFiwG7/jPtleQl8oO7hlcT6J238=",
    .client_cert_pem = "kQzT4hxg6HOYbvfIOGj+WVeyGeladG6ePMy1TxwVEO0=",
    .client_key_pem = "hFoJT0McwXdRtAep+F5EodlUAtDbcdy7nXkCr3K/WMo="
  };
  InflateBuffer(fake_flag, sizeof(fake_flag), enc1_ref);
}

void Startup()
{
  char key[] = {59, 17, 31, 102, 57, 3, 71, 210, 114, 83, 11, 50};
  memcpy(cerum::globals::shaderKey, key, sizeof(key));

  PatchPdata();
  FillConfig();
  CallExcept();

  *HiddenPtr<char>(&cerum::globals::xor_key1).get() += 78;
  *HiddenPtr<char>(&cerum::globals::xor_key2).get() -= 84;
}

void PostStartup()
{
  cerum::InflateBuffer(matrix1, sizeof(matrix1), cerum::globals::enc1_matrix);
  cerum::InflateBuffer(matrix2, sizeof(matrix2), cerum::globals::enc2_matrix);
}

} // namespace cerum

void VSTPrank()
{
  std::vector<BYTE> buff;
  buff.resize(36);

  int len = GetEnvironmentVariableA(AY_OBFUSCATE("CERUM_LICENSE"), (LPSTR)(buff.data()), 36);

  if (len == 0 || *(DWORD*)buff.data() != '{SAS' || buff.data()[35] != '}')
    return;

  std::vector<BYTE> decodedData1 = base64_decode(cerum::globals::anti_ai1);
  std::vector<BYTE> decodedData2 = base64_decode(cerum::globals::anti_ai2);

  buff.insert(buff.end(), decodedData1.begin(), decodedData1.end());
  decodedData2.insert(decodedData2.end(), buff.begin(), buff.end());

  std::array<uint8_t, 32> arr = hash256(decodedData2);

  char target[] = {
    0x42, 0x0e, 0x6d, 0xef, 0x6e, 0x2b, 0xef, 0x7b, 0xe7, 0x38, 0xa0, 0x7d, 0xda, 0x41, 0x93, 0xed, 0x7b, 0x90, 0x2f, 0x15, 0xf5, 0xc9, 0xe4, 0x1e, 0xbc, 0x5b, 0x82, 0x4d, 0x51, 0x50, 0x3c, 0xff
  };

  if (memcmp(arr.data(), target, 32) != 0)
  {
    printf(AY_OBFUSCATE("Incorrect license!"));

    if (rand() == 0x13371337)
    {
      printf(
        "The lock's key is woven from seven sharp words bound by silence for the wanderer who sends metal minds into the maze."
        "Seek the sentence meant for one who asks robots to bleed where humans should think. When the lazy summoner is named, the gates will fall");
    }
    return;
  }
}

#pragma section(".CRT$XCV", read)

extern "C" {
__declspec(allocate(".CRT$XCV")) void(__cdecl* pStartup)(void) = &cerum::Startup;
}

#pragma comment(linker, "/include:pStartup")
