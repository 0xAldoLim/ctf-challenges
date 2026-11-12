#ifndef HWID_HWID_HPP
#define HWID_HWID_HPP

#include <algorithm>
#include <array>
#include <cctype>
#include <cstdint>
#include <iomanip>
#include <map>
#include <sstream>
#include <string>
#include <utility>
#include <vector>

#if defined(_WIN32)
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>
#endif

namespace hwid {

struct fingerprint_result {
  std::string hwid;
  std::map<std::string, std::string> sources;
};

namespace detail {

inline std::string trim_copy(const std::string &input) {
  std::size_t start = 0;
  while (start < input.size() &&
         std::isspace(static_cast<unsigned char>(input[start])) != 0) {
    ++start;
  }

  std::size_t end = input.size();
  while (end > start &&
         std::isspace(static_cast<unsigned char>(input[end - 1])) != 0) {
    --end;
  }

  return input.substr(start, end - start);
}

inline std::string lowercase_copy(std::string value) {
  std::transform(value.begin(), value.end(), value.begin(),
                 [](unsigned char c) { return static_cast<char>(std::tolower(c)); });
  return value;
}

inline std::string normalize_value(const std::string &value) {
  return lowercase_copy(trim_copy(value));
}

inline bool add_source(std::map<std::string, std::string> &sources,
                       const std::string &key, const std::string &raw_value) {
  const std::string value = normalize_value(raw_value);
  if (value.empty()) {
    return false;
  }

  sources.emplace(key, value);
  return true;
}

inline std::string bytes_to_hex(const std::uint8_t *data, std::size_t length) {
  std::ostringstream stream;
  stream << std::hex << std::setfill('0');
  for (std::size_t i = 0; i < length; ++i) {
    stream << std::setw(2) << static_cast<unsigned int>(data[i]);
  }
  return stream.str();
}

inline std::string serialize_sources(const std::map<std::string, std::string> &sources) {
  std::ostringstream stream;
  for (const auto &entry : sources) {
    stream << entry.first << '=' << entry.second << '&';
  }
  stream.seekp(-1, std::ios_base::end);
  return stream.str();
}

inline std::string wide_to_utf8(const std::wstring &value) {
  if (value.empty()) {
    return {};
  }

  const int required =
      WideCharToMultiByte(CP_UTF8, 0, value.c_str(), -1, nullptr, 0, nullptr, nullptr);
  if (required <= 1) {
    return {};
  }

  std::string result(static_cast<std::size_t>(required), '\0');
  WideCharToMultiByte(CP_UTF8, 0, value.c_str(), -1, &result[0], required, nullptr,
                      nullptr);
  result.pop_back();
  return result;
}

inline std::string format_uuid_le(const std::uint8_t *uuid) {
  static constexpr int groups[] = {4, 2, 2, 2, 6};
  std::ostringstream stream;
  stream << std::hex << std::setfill('0');

  int offset = 0;
  for (std::size_t group = 0; group < sizeof(groups) / sizeof(groups[0]); ++group) {
    if (group != 0) {
      stream << '-';
    }
    for (int i = 0; i < groups[group]; ++i) {
      stream << std::setw(2) << static_cast<unsigned int>(uuid[offset++]);
    }
  }

  return stream.str();
}

inline std::string read_registry_string(HKEY root, const wchar_t *subkey,
                                        const wchar_t *value_name) {
  HKEY key = nullptr;
  if (RegOpenKeyExW(root, subkey, 0, KEY_READ | KEY_WOW64_64KEY, &key) != ERROR_SUCCESS) {
    return {};
  }

  DWORD type = 0;
  DWORD size = 0;
  if (RegQueryValueExW(key, value_name, nullptr, &type, nullptr, &size) != ERROR_SUCCESS ||
      (type != REG_SZ && type != REG_EXPAND_SZ)) {
    RegCloseKey(key);
    return {};
  }

  std::wstring buffer(size / sizeof(wchar_t), L'\0');
  if (RegQueryValueExW(key, value_name, nullptr, nullptr,
                       reinterpret_cast<LPBYTE>(&buffer[0]), &size) != ERROR_SUCCESS) {
    RegCloseKey(key);
    return {};
  }
  RegCloseKey(key);

  const auto end = std::find(buffer.begin(), buffer.end(), L'\0');
  buffer.erase(end, buffer.end());
  return wide_to_utf8(buffer);
}

inline std::string get_windows_system_volume_serial() {
  wchar_t windows_directory[MAX_PATH] = L"";
  UINT path_length = GetWindowsDirectoryW(windows_directory, MAX_PATH);
  if (path_length == 0 || path_length >= MAX_PATH) {
    return {};
  }

  wchar_t root_path[] = L"C:\\";
  root_path[0] = windows_directory[0];

  DWORD serial = 0;
  if (!GetVolumeInformationW(root_path, nullptr, 0, &serial, nullptr, nullptr, nullptr, 0)) {
    return {};
  }

  std::ostringstream stream;
  stream << std::hex << std::nouppercase << serial;
  return stream.str();
}

inline std::string get_windows_hardware_profile_guid() {
  HW_PROFILE_INFOW profile{};
  if (!GetCurrentHwProfileW(&profile)) {
    return {};
  }

  return wide_to_utf8(profile.szHwProfileGuid);
}

inline std::string get_windows_smbios_uuid() {
  const UINT size = GetSystemFirmwareTable('RSMB', 0, nullptr, 0);
  if (size < 16) {
    return {};
  }

  std::vector<std::uint8_t> buffer(size);
  if (GetSystemFirmwareTable('RSMB', 0, buffer.data(), size) != size || size < 8) {
    return {};
  }

  const std::size_t data_offset = 8;
  if (buffer.size() <= data_offset) {
    return {};
  }

  std::size_t offset = data_offset;
  while (offset + 4 <= buffer.size()) {
    const std::uint8_t type = buffer[offset];
    const std::uint8_t length = buffer[offset + 1];

    if (length < 4 || offset + length > buffer.size()) {
      break;
    }

    if (type == 1 && length >= 0x19) {
      const std::uint8_t *uuid = &buffer[offset + 8];
      bool all_zero = true;
      bool all_ff = true;
      for (int i = 0; i < 16; ++i) {
        all_zero = all_zero && uuid[i] == 0x00;
        all_ff = all_ff && uuid[i] == 0xff;
      }
      if (!all_zero && !all_ff) {
        std::uint8_t normalized[16] = {
            uuid[3], uuid[2], uuid[1], uuid[0], uuid[5], uuid[4], uuid[7], uuid[6],
            uuid[8], uuid[9], uuid[10], uuid[11], uuid[12], uuid[13], uuid[14], uuid[15]};
        return format_uuid_le(normalized);
      }
    }

    std::size_t next = offset + length;
    while (next + 1 < buffer.size()) {
      if (buffer[next] == 0 && buffer[next + 1] == 0) {
        next += 2;
        break;
      }
      ++next;
    }

    if (next <= offset) {
      break;
    }
    offset = next;
  }

  return {};
}

inline std::map<std::string, std::string> collect_platform_sources() {
  std::map<std::string, std::string> sources;

  add_source(sources, "mg",
             read_registry_string(HKEY_LOCAL_MACHINE,
                                  L"SOFTWARE\\Microsoft\\Cryptography", L"MachineGuid"));
  add_source(sources, "sm", get_windows_smbios_uuid());
  add_source(sources, "hp", get_windows_hardware_profile_guid());
  add_source(sources, "vs", get_windows_system_volume_serial());

  return sources;
}

}  // namespace detail

inline fingerprint_result collect() {
  fingerprint_result result;
  result.sources = detail::collect_platform_sources();
  result.hwid = detail::serialize_sources(result.sources);
  return result;
}

inline std::string get() { return collect().hwid; }

inline int getInt()
{
  std::string hwid = collect().hwid;
  const char* hwidc = hwid.c_str();
  int result = 0xFFFFFFFF;
  int shift = 0;
  for (int i = 0; i < hwid.length(); i++)
  {
    result ^= (hwidc[i] << (shift * 8));
    shift = (shift + 1) % 4;
  }
  return result;
}

}  // namespace hwid

#endif  // HWID_HWID_HPP
