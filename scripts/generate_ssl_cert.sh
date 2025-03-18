#!/bin/bash

# Generate self-signed SSL certificates for LED Grid Web Server
# Usage: ./generate_ssl_cert.sh [domain]

# Configuration
CERT_DIR="$(pwd)/certs"
DOMAIN=${1:-"localhost"}
DAYS=365

# Create certificates directory if it doesn't exist
mkdir -p "$CERT_DIR"

echo "Generating self-signed SSL certificate for domain: $DOMAIN"
echo "Certificates will be saved to: $CERT_DIR"

# Generate private key
openssl genrsa -out "$CERT_DIR/server.key" 2048

# Generate CSR (Certificate Signing Request)
openssl req -new -key "$CERT_DIR/server.key" -out "$CERT_DIR/server.csr" -subj "/CN=$DOMAIN"

# Generate self-signed certificate
openssl x509 -req -days $DAYS -in "$CERT_DIR/server.csr" -signkey "$CERT_DIR/server.key" -out "$CERT_DIR/server.crt"

# Set permissions
chmod 600 "$CERT_DIR/server.key"

echo ""
echo "SSL certificate generation complete!"
echo ""
echo "To use these certificates with LED Grid server, set the following environment variables:"
echo ""
echo "export SSL_CERT=\"$CERT_DIR/server.crt\""
echo "export SSL_KEY=\"$CERT_DIR/server.key\""
echo ""
echo "You can add these to your .env file or source them directly before starting the server."
echo ""
echo "NOTE: These are self-signed certificates and will cause browser warnings."
echo "For production use, consider using Let's Encrypt or another trusted certificate authority." 