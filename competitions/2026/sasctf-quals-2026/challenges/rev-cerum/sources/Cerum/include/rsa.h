#include <string>
#include <vector>
#include <openssl/aes.h>
#include <openssl/evp.h>
#include <openssl/rsa.h>
#include <openssl/pem.h>
#include <openssl/ssl.h>
#include <openssl/bio.h>
#include <openssl/err.h>

bool verify_sign(const char* publicKey, const unsigned char* data, size_t dataLen, const unsigned char* signature, size_t signLen);

