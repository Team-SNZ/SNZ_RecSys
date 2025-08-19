#!/bin/bash

# WiNear 통합 시스템 배포 스크립트

set -e  # 에러 발생 시 스크립트 중단

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 로그 함수들
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 도움말 출력
show_help() {
    echo "WiNear 통합 시스템 배포 스크립트"
    echo ""
    echo "사용법:"
    echo "  $0 [COMMAND] [OPTIONS]"
    echo ""
    echo "Commands:"
    echo "  dev         개발 환경 시작"
    echo "  prod        프로덕션 환경 시작"
    echo "  stop        모든 서비스 중지"
    echo "  restart     서비스 재시작"
    echo "  logs        로그 확인"
    echo "  status      서비스 상태 확인"
    echo "  clean       볼륨 및 이미지 정리"
    echo "  setup       초기 설정 (SSL 인증서 생성 등)"
    echo "  test        API 테스트"
    echo "  help        이 도움말 출력"
    echo ""
    echo "Examples:"
    echo "  $0 dev              # 개발 환경 시작"
    echo "  $0 prod             # 프로덕션 환경 시작"
    echo "  $0 logs api         # API 서비스 로그 확인"
    echo "  $0 test             # API 테스트 실행"
}

# 환경변수 파일 확인
check_env_files() {
    log_info "환경변수 파일을 확인합니다..."
    
    if [ ! -f ".env" ]; then
        log_warning ".env 파일이 없습니다. 템플릿을 생성합니다..."
        cat > .env << EOF
# OpenAI API Key (필수)
WINEAR_OPENAI_API_KEY=sk-your-openai-api-key-here

# 기타 설정 (선택사항)
WINEAR_OPENAI_MODEL=gpt-4o
WINEAR_MONGODB_URI=mongodb://admin:password123@mongodb:27017/travel_recsys?authSource=admin
WINEAR_MONGODB_DB=travel_recsys
EOF
        log_warning ".env 파일을 수정하여 OpenAI API 키를 설정해주세요!"
        return 1
    fi
    
    # OpenAI API 키 확인
    if grep -q "sk-your-openai-api-key-here" .env; then
        log_error "OpenAI API 키가 설정되지 않았습니다. .env 파일을 수정해주세요!"
        return 1
    fi
    
    log_success "환경변수 파일 확인 완료"
}

# 필수 디렉토리 확인
check_directories() {
    log_info "디렉토리 구조를 확인합니다..."
    
    if [ ! -d "../WiNear-backend" ]; then
        log_error "WiNear-backend 디렉토리가 없습니다. 경로를 확인해주세요."
        log_info "현재 디렉토리: $(pwd)"
        log_info "예상 경로: $(dirname $(pwd))/WiNear-backend"
        return 1
    fi
    
    log_success "디렉토리 구조 확인 완료"
}

# SSL 인증서 설정
setup_ssl() {
    log_info "SSL 인증서를 설정합니다..."
    
    if [ ! -d "ssl" ] || [ ! -f "ssl/cert.pem" ]; then
        log_info "SSL 인증서를 생성합니다..."
        ./generate-ssl.sh
    else
        log_info "SSL 인증서가 이미 존재합니다."
    fi
    
    log_success "SSL 인증서 설정 완료"
}

# 초기 설정
setup() {
    log_info "초기 설정을 시작합니다..."
    
    check_env_files || exit 1
    check_directories || exit 1
    setup_ssl
    
    log_success "초기 설정이 완료되었습니다!"
    log_info "이제 'dev' 또는 'prod' 명령으로 시스템을 시작할 수 있습니다."
}

# 개발 환경 시작
start_dev() {
    log_info "개발 환경을 시작합니다..."
    
    check_env_files || exit 1
    check_directories || exit 1
    
    # SSL 인증서가 없으면 생성
    if [ ! -f "ssl/cert.pem" ]; then
        setup_ssl
    fi
    
    log_info "Docker Compose로 개발 환경을 시작합니다..."
    docker-compose up -d
    
    log_success "개발 환경이 시작되었습니다!"
    log_info "서비스 URL:"
    log_info "  • API Gateway: https://localhost"
    log_info "  • WiNear API: https://localhost/api/ (또는 http://localhost:8001)"
    log_info "  • RecSys Agent: https://localhost/recsys/ (또는 http://localhost:8002)"
    log_info "  • API 문서: https://localhost/docs (WiNear), https://localhost/recsys/docs (RecSys)"
    log_info "  • MongoDB: localhost:27017"
}

# 프로덕션 환경 시작
start_prod() {
    log_info "프로덕션 환경을 시작합니다..."
    
    check_env_files || exit 1
    check_directories || exit 1
    
    log_info "Docker Compose로 프로덕션 환경을 시작합니다..."
    docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
    
    log_success "프로덕션 환경이 시작되었습니다!"
    log_info "서비스 URL:"
    log_info "  • API Gateway: https://localhost"
    log_info "  • API 문서: https://localhost/docs"
}

# 서비스 중지
stop() {
    log_info "모든 서비스를 중지합니다..."
    docker-compose down
    log_success "모든 서비스가 중지되었습니다."
}

# 서비스 재시작
restart() {
    log_info "서비스를 재시작합니다..."
    docker-compose restart
    log_success "서비스가 재시작되었습니다."
}

# 로그 확인
show_logs() {
    if [ -n "$2" ]; then
        log_info "$2 서비스의 로그를 확인합니다..."
        docker-compose logs -f "$2"
    else
        log_info "모든 서비스의 로그를 확인합니다..."
        docker-compose logs -f
    fi
}

# 서비스 상태 확인
show_status() {
    log_info "서비스 상태를 확인합니다..."
    echo ""
    docker-compose ps
    echo ""
    
    # API 상태 확인
    log_info "API 상태를 확인합니다..."
    
    # 직접 포트로 헬스체크
    if curl -s http://localhost:8001/health > /dev/null 2>&1; then
        log_success "WiNear API: 정상"
    else
        log_error "WiNear API: 비정상"
    fi
    
    if curl -s http://localhost:8002/health > /dev/null 2>&1; then
        log_success "RecSys Agent: 정상"
    else
        log_error "RecSys Agent: 비정상"
    fi
    
    # Gateway를 통한 헬스체크
    if curl -s -k https://localhost/health > /dev/null 2>&1; then
        log_success "API Gateway: 정상"
    else
        log_warning "API Gateway: 확인 불가 (SSL 인증서 문제일 수 있음)"
    fi
}

# 정리
clean() {
    log_warning "모든 컨테이너, 볼륨, 이미지를 정리합니다..."
    read -p "계속하시겠습니까? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        docker-compose down -v
        docker system prune -f
        log_success "정리가 완료되었습니다."
    else
        log_info "정리가 취소되었습니다."
    fi
}

# API 테스트
test_api() {
    log_info "API 테스트를 실행합니다..."
    
    # WiNear API 테스트
    log_info "WiNear API 헬스체크..."
    if curl -s http://localhost:8001/health | jq . > /dev/null 2>&1; then
        log_success "WiNear API: OK"
    else
        log_error "WiNear API: Failed"
    fi
    
    # RecSys Agent 테스트
    log_info "RecSys Agent 헬스체크..."
    if curl -s http://localhost:8002/health | jq . > /dev/null 2>&1; then
        log_success "RecSys Agent: OK"
    else
        log_error "RecSys Agent: Failed"
    fi
    
    # Gateway 테스트
    log_info "API Gateway 테스트..."
    if curl -s -k https://localhost/health | jq . > /dev/null 2>&1; then
        log_success "API Gateway: OK"
    else
        log_warning "API Gateway: Check manually (SSL certificate)"
    fi
    
    # 추천 API 테스트 (샘플)
    log_info "추천 API 테스트..."
    TEST_RESPONSE=$(curl -s -X POST "http://localhost:8002/agent/recommend" \
        -H "Content-Type: application/json" \
        -d '{"user_id": "test_user"}' | jq -r '.status' 2>/dev/null)
    
    if [ "$TEST_RESPONSE" = "success" ]; then
        log_success "추천 API: OK"
    else
        log_warning "추천 API: Failed (데이터가 없을 수 있음)"
    fi
}

# 메인 로직
case "$1" in
    "dev")
        start_dev
        ;;
    "prod")
        start_prod
        ;;
    "stop")
        stop
        ;;
    "restart")
        restart
        ;;
    "logs")
        show_logs "$@"
        ;;
    "status")
        show_status
        ;;
    "clean")
        clean
        ;;
    "setup")
        setup
        ;;
    "test")
        test_api
        ;;
    "help"|"--help"|"-h")
        show_help
        ;;
    "")
        log_error "명령을 지정해주세요."
        show_help
        exit 1
        ;;
    *)
        log_error "알 수 없는 명령: $1"
        show_help
        exit 1
        ;;
esac
