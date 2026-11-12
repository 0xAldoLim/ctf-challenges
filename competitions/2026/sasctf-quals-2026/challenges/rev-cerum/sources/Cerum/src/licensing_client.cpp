#include "licensing_client.hpp"

#include <algorithm>
#include <array>
#include <cerrno>
#include <cstddef>
#include <cstdint>
#include <cstring>
#include <map>
#include <memory>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

#include <openssl/err.h>
#include <openssl/hmac.h>
#include <openssl/pem.h>
#include <openssl/rand.h>
#include <openssl/ssl.h>

#ifdef _WIN32
  #include <winsock2.h>
  #include <ws2tcpip.h>
  #pragma comment(lib, "ws2_32.lib")
#else
  #include <arpa/inet.h>
  #include <netdb.h>
  #include <sys/socket.h>
  #include <unistd.h>
#endif

namespace lic
{
namespace
{

constexpr char kMagic[4] = {'c', 'L', 'I', 'C'};
constexpr std::uint8_t kVersion = 1;
constexpr std::uint8_t kTypeError = 0;
constexpr std::uint8_t kTypeActivate = 1;
constexpr std::uint8_t kTypeValidate = 2;
constexpr std::size_t kHeaderSize = 32;
constexpr std::size_t kMacSize = 32;

using SocketHandle = SOCKET;
constexpr SocketHandle kInvalidSocket = INVALID_SOCKET;

class SocketRuntime
{
public:
  SocketRuntime()
  {
    WSADATA wsa_data{};
    if (WSAStartup(MAKEWORD(2, 2), &wsa_data) != 0)
      throw -1;
  }

  ~SocketRuntime()
  {
    WSACleanup();
  }
};

SocketRuntime& socketRuntime()
{
  static SocketRuntime runtime;
  return runtime;
}

void closeSocket(SocketHandle socket_handle) noexcept
{
  if (socket_handle == kInvalidSocket)
  {
    return;
  }
  closesocket(socket_handle);
}

std::vector<std::uint8_t> hmacSha256(const std::vector<std::uint8_t>& key, const std::vector<std::uint8_t>& data)
{
  unsigned int length = 0;
  std::vector<std::uint8_t> digest(EVP_MAX_MD_SIZE);
  if (HMAC(EVP_sha256(), key.data(), static_cast<int>(key.size()), data.data(), data.size(), digest.data(), &length) == nullptr)
    throw -1;
  digest.resize(length);
  return digest;
}

std::vector<std::uint8_t> hmacSha256(const std::vector<std::uint8_t>& key, const std::string& data)
{
  return hmacSha256(key, std::vector<std::uint8_t>(data.begin(), data.end()));
}

std::vector<std::uint8_t> deriveKey(const std::string& shared_secret, const std::string& label)
{
  const std::vector<std::uint8_t> secret_bytes(shared_secret.begin(), shared_secret.end());
  return hmacSha256(secret_bytes, label);
}

BIO* newPemBio(const std::string& pem) { return BIO_new_mem_buf(pem.data(), static_cast<int>(pem.size())); }

void loadVerifyCaFromPem(SSL_CTX* ssl_ctx, const std::string& pem)
{
  std::unique_ptr<BIO, decltype(&BIO_free)> bio(newPemBio(pem), BIO_free);
  if (!bio)
    throw -1;

  X509_STORE* store = SSL_CTX_get_cert_store(ssl_ctx);
  if (store == nullptr)
    throw -1;

  bool loaded_any = false;
  while (true)
  {
    X509* cert = PEM_read_bio_X509(bio.get(), nullptr, nullptr, nullptr);
    if (cert == nullptr)
      break;
    loaded_any = true;
    if (X509_STORE_add_cert(store, cert) != 1)
    {
      const unsigned long error = ERR_peek_last_error();
      const unsigned long duplicate_error = ERR_PACK(ERR_LIB_X509, 0, X509_R_CERT_ALREADY_IN_HASH_TABLE);
      X509_free(cert);
      if (error != duplicate_error)
        throw -1;
      ERR_clear_error();
      continue;
    }
    X509_free(cert);
  }

  if (!loaded_any)
  {
    ERR_clear_error();
    throw -1;
  }
  ERR_clear_error();
}

void loadClientCertificateFromPem(SSL_CTX* ssl_ctx, const std::string& pem)
{
  std::unique_ptr<BIO, decltype(&BIO_free)> bio(newPemBio(pem), BIO_free);
  if (!bio)
    throw -1;

  X509* leaf = PEM_read_bio_X509(bio.get(), nullptr, nullptr, nullptr);
  if (leaf == nullptr)
    throw -1;
  if (SSL_CTX_use_certificate(ssl_ctx, leaf) != 1)
  {
    X509_free(leaf);
    throw -1;
  }
  X509_free(leaf);

  while (true)
  {
    X509* extra = PEM_read_bio_X509(bio.get(), nullptr, nullptr, nullptr);
    if (extra == nullptr)
    {
      break;
    }
    if (SSL_CTX_add_extra_chain_cert(ssl_ctx, extra) != 1)
    {
      X509_free(extra);
      throw -1;
    }
  }
  ERR_clear_error();
}

void loadClientKeyFromPem(SSL_CTX* ssl_ctx, const std::string& pem)
{
  std::unique_ptr<BIO, decltype(&BIO_free)> bio(newPemBio(pem), BIO_free);
  if (!bio)
    throw -1;

  EVP_PKEY* key = PEM_read_bio_PrivateKey(bio.get(), nullptr, nullptr, nullptr);
  if (key == nullptr)
    throw -1;
  if (SSL_CTX_use_PrivateKey(ssl_ctx, key) != 1)
  {
    EVP_PKEY_free(key);
    throw -1;
  }
  EVP_PKEY_free(key);
}

std::vector<std::uint8_t> xorStreamCrypt(const std::vector<std::uint8_t>& key, const std::array<std::uint8_t, 16>& nonce, const std::vector<std::uint8_t>& payload)
{
  std::vector<std::uint8_t> output(payload.size());
  std::size_t offset = 0;
  std::uint32_t counter = 0;

  while (offset < payload.size())
  {
    std::vector<std::uint8_t> input(nonce.begin(), nonce.end());
    input.push_back(static_cast<std::uint8_t>(counter & 0xFF));
    input.push_back(static_cast<std::uint8_t>((counter >> 8) & 0xFF));
    input.push_back(static_cast<std::uint8_t>((counter >> 16) & 0xFF));
    input.push_back(static_cast<std::uint8_t>((counter >> 24) & 0xFF));

    const std::vector<std::uint8_t> block = hmacSha256(key, input);
    const std::size_t take = std::min<std::size_t>(block.size(), payload.size() - offset);
    for (std::size_t i = 0; i < take; ++i)
    {
      output[offset + i] = payload[offset + i] ^ block[i];
    }
    offset += take;
    ++counter;
  }

  return output;
}

void appendLe16(std::vector<std::uint8_t>& buffer, std::uint16_t value)
{
  buffer.push_back(static_cast<std::uint8_t>(value & 0xFF));
  buffer.push_back(static_cast<std::uint8_t>((value >> 8) & 0xFF));
}

void appendLe32(std::vector<std::uint8_t>& buffer, std::uint32_t value)
{
  buffer.push_back(static_cast<std::uint8_t>(value & 0xFF));
  buffer.push_back(static_cast<std::uint8_t>((value >> 8) & 0xFF));
  buffer.push_back(static_cast<std::uint8_t>((value >> 16) & 0xFF));
  buffer.push_back(static_cast<std::uint8_t>((value >> 24) & 0xFF));
}

void appendLe64(std::vector<std::uint8_t>& buffer, std::uint64_t value)
{
  for (int shift = 0; shift < 64; shift += 8)
  {
    buffer.push_back(static_cast<std::uint8_t>((value >> shift) & 0xFF));
  }
}

void appendBytes(std::vector<std::uint8_t>& buffer, const std::vector<std::uint8_t>& value)
{
  appendLe32(buffer, static_cast<std::uint32_t>(value.size()));
  buffer.insert(buffer.end(), value.begin(), value.end());
}

void appendString(std::vector<std::uint8_t>& buffer, const std::string& value)
{
  appendLe32(buffer, static_cast<std::uint32_t>(value.size()));
  buffer.insert(buffer.end(), value.begin(), value.end());
}

std::uint16_t readLe16(const std::uint8_t* data) { return static_cast<std::uint16_t>(data[0] | (static_cast<std::uint16_t>(data[1]) << 8)); }

std::uint32_t readLe32(const std::uint8_t* data)
{
  return static_cast<std::uint32_t>(data[0] | (static_cast<std::uint32_t>(data[1]) << 8) | (static_cast<std::uint32_t>(data[2]) << 16) | (static_cast<std::uint32_t>(data[3]) << 24));
}

std::uint64_t readLe64(const std::uint8_t* data)
{
  std::uint64_t value = 0;
  for (int shift = 0; shift < 64; shift += 8)
  {
    value |= static_cast<std::uint64_t>(data[shift / 8]) << shift;
  }
  return value;
}

class BinaryReader
{
public:
  explicit BinaryReader(const std::vector<std::uint8_t>& buffer)
    : buffer_(buffer)
  {
  }

  std::uint32_t readU32()
  {
    ensureAvailable(4);
    const std::uint32_t value = readLe32(buffer_.data() + offset_);
    offset_ += 4;
    return value;
  }

  std::int64_t readI64()
  {
    ensureAvailable(8);
    const std::int64_t value = static_cast<std::int64_t>(readLe64(buffer_.data() + offset_));
    offset_ += 8;
    return value;
  }

  std::string readString()
  {
    const std::uint32_t size = readU32();
    ensureAvailable(size);
    std::string value(buffer_.begin() + offset_, buffer_.begin() + offset_ + size);
    offset_ += size;
    return value;
  }

  std::vector<std::uint8_t> readBytes()
  {
    const std::uint32_t size = readU32();
    ensureAvailable(size);
    std::vector<std::uint8_t> value(buffer_.begin() + offset_, buffer_.begin() + offset_ + size);
    offset_ += size;
    return value;
  }

  std::vector<std::uint8_t> readFixedBytes(std::size_t size)
  {
    ensureAvailable(size);
    std::vector<std::uint8_t> value(buffer_.begin() + offset_, buffer_.begin() + offset_ + size);
    offset_ += size;
    return value;
  }

  void ensureFullyConsumed() const
  {
    if (offset_ != buffer_.size())
      throw -1;
  }

private:
  void ensureAvailable(std::size_t size) const
  {
    if (offset_ + size > buffer_.size())
      throw -1;
  }

  const std::vector<std::uint8_t>& buffer_;
  std::size_t offset_ = 0;
};

std::vector<std::uint8_t> buildFrame(
  std::uint8_t msg_type, std::uint32_t request_id, const std::vector<std::uint8_t>& payload, const std::vector<std::uint8_t>& enc_key, const std::vector<std::uint8_t>& mac_key)
{
  std::array<std::uint8_t, 16> nonce{};
  if (RAND_bytes(nonce.data(), static_cast<int>(nonce.size())) != 1)
    throw -1;

  const std::vector<std::uint8_t> ciphertext = xorStreamCrypt(enc_key, nonce, payload);

  std::vector<std::uint8_t> frame;
  frame.reserve(kHeaderSize + ciphertext.size() + kMacSize);
  frame.insert(frame.end(), kMagic, kMagic + 4);
  frame.push_back(kVersion);
  frame.push_back(msg_type);
  appendLe16(frame, 0);
  appendLe32(frame, request_id);
  frame.insert(frame.end(), nonce.begin(), nonce.end());
  appendLe32(frame, static_cast<std::uint32_t>(ciphertext.size()));
  frame.insert(frame.end(), ciphertext.begin(), ciphertext.end());

  const std::vector<std::uint8_t> mac = hmacSha256(mac_key, frame);
  frame.insert(frame.end(), mac.begin(), mac.end());
  return frame;
}

struct DecodedFrame
{
  std::uint8_t msg_type = 0;
  std::uint32_t request_id = 0;
  std::vector<std::uint8_t> payload;
};

SocketHandle connectSocket(const std::string& host, std::uint16_t port)
{
  socketRuntime();

  addrinfo hints{};
  hints.ai_socktype = SOCK_STREAM;
  hints.ai_family = AF_UNSPEC;

  addrinfo* result = nullptr;
  const std::string port_string = std::to_string(port);
  if (getaddrinfo(host.c_str(), port_string.c_str(), &hints, &result) != 0)
    throw -1;

  SocketHandle connected_socket = kInvalidSocket;
  for (addrinfo* current = result; current != nullptr; current = current->ai_next)
  {
    connected_socket = socket(current->ai_family, current->ai_socktype, current->ai_protocol);
    if (connected_socket == kInvalidSocket)
      continue;
    if (::connect(connected_socket, current->ai_addr, static_cast<int>(current->ai_addrlen)) == 0)
      break;
    closeSocket(connected_socket);
    connected_socket = kInvalidSocket;
  }

  freeaddrinfo(result);

  if (connected_socket == kInvalidSocket)
    throw -1;

  return connected_socket;
}

void sslWriteAll(SSL* ssl, const std::vector<std::uint8_t>& data)
{
  std::size_t offset = 0;
  while (offset < data.size())
  {
    const int written = SSL_write(ssl, data.data() + offset, static_cast<int>(data.size() - offset));
    if (written <= 0)
      throw -1;
    offset += static_cast<std::size_t>(written);
  }
}

std::vector<std::uint8_t> sslReadExact(SSL* ssl, std::size_t size)
{
  std::vector<std::uint8_t> buffer(size);
  std::size_t offset = 0;
  while (offset < size)
  {
    const int received = SSL_read(ssl, buffer.data() + offset, static_cast<int>(size - offset));
    if (received <= 0)
      throw -1;
    offset += static_cast<std::size_t>(received);
  }
  return buffer;
}

DecodedFrame readFrame(SSL* ssl, const std::vector<std::uint8_t>& enc_key, const std::vector<std::uint8_t>& mac_key)
{
  const std::vector<std::uint8_t> header = sslReadExact(ssl, kHeaderSize);
  if (!std::equal(header.begin(), header.begin() + 4, reinterpret_cast<const std::uint8_t*>(kMagic)))
    throw -1;
  if (header[4] != kVersion)
    throw -1;

  const std::uint8_t msg_type = header[5];
  const std::uint16_t flags = readLe16(header.data() + 6);
  (void)flags;
  const std::uint32_t request_id = readLe32(header.data() + 8);
  std::array<std::uint8_t, 16> nonce{};
  std::copy(header.begin() + 12, header.begin() + 28, nonce.begin());
  const std::uint32_t payload_len = readLe32(header.data() + 28);

  const std::vector<std::uint8_t> ciphertext = sslReadExact(ssl, payload_len);
  const std::vector<std::uint8_t> mac = sslReadExact(ssl, kMacSize);

  std::vector<std::uint8_t> signed_data = header;
  signed_data.insert(signed_data.end(), ciphertext.begin(), ciphertext.end());
  const std::vector<std::uint8_t> expected_mac = hmacSha256(mac_key, signed_data);
  if (expected_mac != mac)
    throw -1;

  return DecodedFrame{msg_type, request_id, xorStreamCrypt(enc_key, nonce, ciphertext)};
}

ActivationResponse parseActivationResponse(const DecodedFrame& frame)
{
  BinaryReader reader(frame.payload);

  ActivationResponse response;

  response.sys_size = reader.readU32();

  response.rhs1_gzip = reader.readBytes();
  response.rhs2_gzip = reader.readBytes();

  response.offline_check = reader.readBytes();
  response.signature = reader.readBytes();

  reader.ensureFullyConsumed();
  return response;
}

} // namespace

class LicenseClient::Impl
{
public:
  explicit Impl(const ClientConfig& config)
    : config_(config)
    , enc_key_(deriveKey(config.shared_secret, "lic-server-enc"))
    , mac_key_(deriveKey(config.shared_secret, "lic-server-mac"))
  {
    SSL_library_init();
    SSL_load_error_strings();
    OpenSSL_add_ssl_algorithms();
  }

  ~Impl() { close(); }

  void connect()
  {
    if (ssl_ != nullptr)
      return;

    socket_ = connectSocket(config_.host, config_.port);

    ssl_ctx_ = SSL_CTX_new(TLS_client_method());
    if (ssl_ctx_ == nullptr)
    {
      close();
      throw -1;
    }

    SSL_CTX_set_verify(ssl_ctx_, SSL_VERIFY_PEER, nullptr);
    SSL_CTX_set_default_verify_paths(ssl_ctx_);

    loadVerifyCaFromPem(ssl_ctx_, config_.ca_cert_pem);

    loadClientCertificateFromPem(ssl_ctx_, config_.client_cert_pem);
    loadClientKeyFromPem(ssl_ctx_, config_.client_key_pem);

    if (SSL_CTX_check_private_key(ssl_ctx_) != 1)
    {
      close();
      throw -1;
    }

    ssl_ = SSL_new(ssl_ctx_);
    if (ssl_ == nullptr)
    {
      close();
      throw -1;
    }

    SSL_set_fd(ssl_, static_cast<int>(socket_));
    if (!config_.server_name.empty())
      SSL_set_tlsext_host_name(ssl_, config_.server_name.c_str());
    else
      SSL_set_tlsext_host_name(ssl_, config_.host.c_str());

    if (SSL_connect(ssl_) != 1)
    {
      close();
      throw -1;
    }

    const long verify_result = SSL_get_verify_result(ssl_);
    if (verify_result != X509_V_OK)
    {
      close();
      throw -1;
    }
  }

  void close() noexcept
  {
    if (ssl_ != nullptr)
    {
      SSL_shutdown(ssl_);
      SSL_free(ssl_);
      ssl_ = nullptr;
    }
    if (ssl_ctx_ != nullptr)
    {
      SSL_CTX_free(ssl_ctx_);
      ssl_ctx_ = nullptr;
    }
    if (socket_ != kInvalidSocket)
    {
      closeSocket(socket_);
      socket_ = kInvalidSocket;
    }
  }

  bool isConnected() const noexcept { return ssl_ != nullptr; }

  ActivationResponse activate(const ActivationRequest& request)
  {
    ensureConnected();

    std::vector<std::uint8_t> payload;
    appendString(payload, request.vst_host);
    appendString(payload, request.license_key);
    appendString(payload, request.hwid);

    const DecodedFrame frame = transact(kTypeActivate, payload);
    if (frame.msg_type == kTypeError)
      throw -1;
    if (frame.msg_type != kTypeActivate)
      throw -1;
    return parseActivationResponse(frame);
  }

private:
  void ensureConnected()
  {
    if (!isConnected())
      connect();
  }

  DecodedFrame transact(std::uint8_t msg_type, const std::vector<std::uint8_t>& payload)
  {
    const std::vector<std::uint8_t> frame = buildFrame(msg_type, next_request_id_++, payload, enc_key_, mac_key_);
    sslWriteAll(ssl_, frame);
    return readFrame(ssl_, enc_key_, mac_key_);
  }

  ClientConfig config_;
  std::vector<std::uint8_t> enc_key_;
  std::vector<std::uint8_t> mac_key_;
  SocketHandle socket_ = kInvalidSocket;
  SSL_CTX* ssl_ctx_ = nullptr;
  SSL* ssl_ = nullptr;
  std::uint32_t next_request_id_ = 1;
};

LicenseClient::LicenseClient(const ClientConfig& config)
  : impl_(std::make_unique<Impl>(config))
{ }

LicenseClient::~LicenseClient() = default;

LicenseClient::LicenseClient(LicenseClient&&) noexcept = default;

LicenseClient& LicenseClient::operator=(LicenseClient&&) noexcept = default;

void LicenseClient::connect() { impl_->connect(); }

void LicenseClient::close() { impl_->close(); }

bool LicenseClient::isConnected() const noexcept { return impl_->isConnected(); }

ActivationResponse LicenseClient::activate(const ActivationRequest& request) { return impl_->activate(request); }

} // namespace lic
