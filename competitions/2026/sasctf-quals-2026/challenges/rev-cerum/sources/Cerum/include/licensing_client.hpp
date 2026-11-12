#pragma once

#include <cstdint>
#include <map>
#include <memory>
#include <string>
#include <vector>

namespace lic
{

struct ClientConfig
{
  std::string host;
  std::uint16_t port;
  std::string shared_secret;
  std::string server_name;
  std::string ca_cert_pem;
  std::string client_cert_pem;
  std::string client_key_pem;
};

struct ActivationRequest
{
  std::string vst_host;
  std::string license_key;
  std::string hwid;
};

struct ActivationResponse
{
  uint32_t sys_size;
  std::vector<std::uint8_t> rhs1_gzip;
  std::vector<std::uint8_t> rhs2_gzip;
  std::vector<std::uint8_t> offline_check;
  std::vector<std::uint8_t> signature;
};

class LicenseClient
{
public:
  explicit LicenseClient(const ClientConfig& config);
  ~LicenseClient();

  LicenseClient(const LicenseClient&) = delete;
  LicenseClient& operator=(const LicenseClient&) = delete;

  LicenseClient(LicenseClient&&) noexcept;
  LicenseClient& operator=(LicenseClient&&) noexcept;

  void connect();
  void close();
  bool isConnected() const noexcept;

  ActivationResponse activate(const ActivationRequest& request);

private:
  class Impl;
  std::unique_ptr<Impl> impl_;
};

} // namespace lic
