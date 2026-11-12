#!/bin/sh
set -e

CERT_DIR=/etc/ssl/wallet
mkdir -p "$CERT_DIR"

if [ ! -f "$CERT_DIR/cert.pem" ]; then
    openssl req -x509 -newkey rsa:2048 -nodes \
        -keyout "$CERT_DIR/key.pem" \
        -out "$CERT_DIR/cert.pem" \
        -days 365 \
        -subj "/C=US/ST=CA/L=SF/O=CryptoCloud Inc/CN=cryptowallet.ctf" \
        -addext "subjectAltName=DNS:cryptowallet.ctf,IP:10.0.2.80"
fi

gunicorn app:app \
    --bind 0.0.0.0:80 \
    --certfile "$CERT_DIR/cert.pem" \
    --keyfile "$CERT_DIR/key.pem" \
    --bind 0.0.0.0:443 \
    --workers 2 \
    --access-logfile - \
    --error-logfile -
