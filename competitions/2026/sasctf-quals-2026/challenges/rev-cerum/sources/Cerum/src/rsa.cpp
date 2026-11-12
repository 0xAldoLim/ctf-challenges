#include "rsa.h"

bool verify_sign(const char* publicKey, const unsigned char* data, size_t dataLen, const unsigned char* signature, size_t signLen)
{
  bool ok = false;

  BIO* keybio = BIO_new_mem_buf(publicKey, -1);
  if (!keybio)
    return false;

  EVP_PKEY* raw_key = PEM_read_bio_PUBKEY(keybio, nullptr, nullptr, nullptr);
  if (!raw_key)
  {
    BIO_free(keybio);
    return false;
  }

  EVP_MD_CTX* mdctx = EVP_MD_CTX_new();
  if (!mdctx)
  {
    EVP_PKEY_free(raw_key);
    BIO_free(keybio);
    return false;
  }

  EVP_PKEY_CTX* pkey_ctx = nullptr;

  if (EVP_DigestVerifyInit(mdctx, &pkey_ctx, EVP_sha256(), nullptr, raw_key) != 1)
    goto cleanup;

  if (EVP_PKEY_CTX_set_rsa_padding(pkey_ctx, RSA_PKCS1_PSS_PADDING) <= 0)
    goto cleanup;

  if (EVP_PKEY_CTX_set_rsa_mgf1_md(pkey_ctx, EVP_sha256()) <= 0)
    goto cleanup;

  if (EVP_PKEY_CTX_set_rsa_pss_saltlen(pkey_ctx, RSA_PSS_SALTLEN_DIGEST) <= 0)
    goto cleanup;

  if (EVP_DigestVerifyUpdate(mdctx, data, dataLen) != 1)
    goto cleanup;

  ok = (EVP_DigestVerifyFinal(mdctx, signature, signLen) == 1);

cleanup:
  EVP_MD_CTX_free(mdctx);
  EVP_PKEY_free(raw_key);
  BIO_free(keybio);

  return ok;
}