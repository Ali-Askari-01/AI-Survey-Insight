#!/bin/bash
# ═══════════════════════════════════════════════════
# SSL Certificate Generation Script
# ═══════════════════════════════════════════════════
# Usage:
#   ./generate-certs.sh                    # Self-signed (dev/testing)
#   ./generate-certs.sh --letsencrypt      # Let's Encrypt (production)
#
# Self-signed certs work for local dev / internal testing.
# For production, use Let's Encrypt (free, auto-renewing).
# ═══════════════════════════════════════════════════

set -e

SSL_DIR="$(dirname "$0")/ssl"
mkdir -p "$SSL_DIR"

if [ "$1" = "--letsencrypt" ]; then
    # ── Let's Encrypt (Production) ──
    if [ -z "$2" ]; then
        echo "Usage: ./generate-certs.sh --letsencrypt yourdomain.com"
        exit 1
    fi
    DOMAIN="$2"
    echo "🔒 Requesting Let's Encrypt certificate for $DOMAIN..."
    
    # Install certbot if not present
    if ! command -v certbot &> /dev/null; then
        echo "Installing certbot..."
        apt-get update && apt-get install -y certbot
    fi
    
    # Generate certificate (standalone mode — stop nginx first)
    certbot certonly --standalone -d "$DOMAIN" --non-interactive --agree-tos --email "admin@$DOMAIN"
    
    # Copy certs to nginx ssl directory
    cp "/etc/letsencrypt/live/$DOMAIN/fullchain.pem" "$SSL_DIR/cert.pem"
    cp "/etc/letsencrypt/live/$DOMAIN/privkey.pem" "$SSL_DIR/key.pem"
    
    echo "✅ Let's Encrypt certificate installed for $DOMAIN"
    echo "   Certificate: $SSL_DIR/cert.pem"
    echo "   Private Key: $SSL_DIR/key.pem"
    echo ""
    echo "⏰ Auto-renewal: Add this cron job:"
    echo "   0 0 1 * * certbot renew --quiet && cp /etc/letsencrypt/live/$DOMAIN/fullchain.pem $SSL_DIR/cert.pem && cp /etc/letsencrypt/live/$DOMAIN/privkey.pem $SSL_DIR/key.pem && docker-compose restart nginx"
else
    # ── Self-Signed (Development) ──
    echo "🔒 Generating self-signed SSL certificate for local development..."
    
    openssl req -x509 -nodes -days 365 \
        -newkey rsa:2048 \
        -keyout "$SSL_DIR/key.pem" \
        -out "$SSL_DIR/cert.pem" \
        -subj "/C=US/ST=Dev/L=Local/O=AI-Survey/CN=localhost" \
        -addext "subjectAltName=DNS:localhost,IP:127.0.0.1"
    
    echo "✅ Self-signed certificate generated"
    echo "   Certificate: $SSL_DIR/cert.pem"
    echo "   Private Key: $SSL_DIR/key.pem"
    echo ""
    echo "⚠️  Browsers will show a security warning for self-signed certs."
    echo "   For production, run: ./generate-certs.sh --letsencrypt yourdomain.com"
fi

# Set secure permissions
chmod 644 "$SSL_DIR/cert.pem"
chmod 600 "$SSL_DIR/key.pem"

echo "🚀 Restart nginx to apply: docker-compose restart nginx"
