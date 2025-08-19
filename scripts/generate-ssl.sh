#!/bin/bash

# 개발환경용 Self-Signed SSL 인증서 생성 스크립트

SSL_DIR="./ssl"
CERT_FILE="$SSL_DIR/cert.pem"
KEY_FILE="$SSL_DIR/key.pem"

# SSL 디렉토리 생성
mkdir -p $SSL_DIR

# 기존 인증서가 있으면 백업
if [ -f "$CERT_FILE" ]; then
    echo "기존 인증서를 백업합니다..."
    mv "$CERT_FILE" "$CERT_FILE.backup.$(date +%Y%m%d_%H%M%S)"
    mv "$KEY_FILE" "$KEY_FILE.backup.$(date +%Y%m%d_%H%M%S)"
fi

# Self-Signed 인증서 생성
echo "Self-Signed SSL 인증서를 생성합니다..."
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
    -keyout "$KEY_FILE" \
    -out "$CERT_FILE" \
    -subj "/C=KR/ST=Seoul/L=Seoul/O=WiNear/OU=Development/CN=localhost" \
    -addext "subjectAltName=DNS:localhost,DNS:*.localhost,IP:127.0.0.1,IP:0.0.0.0"

# 권한 설정
chmod 600 "$KEY_FILE"
chmod 644 "$CERT_FILE"

echo "SSL 인증서가 생성되었습니다:"
echo "  Certificate: $CERT_FILE"
echo "  Private Key: $KEY_FILE"
echo ""
echo "⚠️  이는 개발용 Self-Signed 인증서입니다."
echo "   프로덕션에서는 Let's Encrypt나 상용 인증서를 사용하세요."
echo ""
echo "브라우저에서 https://localhost 접속 시 보안 경고가 나타날 수 있습니다."
echo "개발환경에서는 '고급 설정' → '안전하지 않은 사이트로 이동'을 선택하세요."
