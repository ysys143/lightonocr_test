#!/bin/bash

# LightOnOCR llama.cpp 설치 스크립트
# macOS 사용자를 위한 완전 자동 설치

set -e

echo "=================================="
echo "LightOnOCR 설치 시작"
echo "=================================="
echo ""

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 함수: 성공 메시지
success() {
    echo -e "${GREEN}✓${NC} $1"
}

# 함수: 경고 메시지
warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

# 함수: 에러 메시지
error() {
    echo -e "${RED}✗${NC} $1"
}

# 1. Homebrew 설치 확인
echo "1. Homebrew 확인 중..."
if command -v brew &> /dev/null; then
    success "Homebrew가 이미 설치되어 있습니다"
    brew_version=$(brew --version | head -n 1)
    echo "   $brew_version"
else
    warning "Homebrew가 설치되어 있지 않습니다"
    echo "   다음 명령어로 Homebrew를 먼저 설치해주세요:"
    echo ""
    echo '   /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"'
    echo ""
    echo "   설치 후 다시 이 스크립트를 실행해주세요."
    exit 1
fi
echo ""

# 2. Xcode Command Line Tools 확인
echo "2. Xcode Command Line Tools 확인 중..."
if xcode-select -p &> /dev/null; then
    success "Xcode Command Line Tools가 설치되어 있습니다"
else
    warning "Xcode Command Line Tools를 설치합니다..."
    xcode-select --install
    echo "   설치가 완료되면 다시 이 스크립트를 실행해주세요."
    exit 1
fi
echo ""

# 3. llama.cpp 설치
echo "3. llama.cpp 설치 중..."
if brew list llama.cpp &> /dev/null; then
    success "llama.cpp가 이미 설치되어 있습니다"
    echo "   최신 버전으로 업데이트 확인 중..."
    brew upgrade llama.cpp 2>/dev/null || true
else
    echo "   llama.cpp를 설치합니다..."
    brew install llama.cpp
    success "llama.cpp 설치 완료"
fi

# llama-server 경로 확인
LLAMA_SERVER_PATH=$(which llama-server)
if [ -z "$LLAMA_SERVER_PATH" ]; then
    error "llama-server를 찾을 수 없습니다"
    exit 1
fi
success "llama-server 위치: $LLAMA_SERVER_PATH"
echo ""

# 4. Python 설치 확인
echo "4. Python 환경 확인 중..."
if command -v python3 &> /dev/null; then
    python_version=$(python3 --version)
    success "Python이 설치되어 있습니다: $python_version"
else
    warning "Python이 설치되어 있지 않습니다"
    echo "   Python을 설치합니다..."
    brew install python@3.12
    success "Python 설치 완료"
fi
echo ""

# 5. uv 설치 확인
echo "5. uv (Python 패키지 관리자) 확인 중..."
if command -v uv &> /dev/null; then
    success "uv가 이미 설치되어 있습니다"
else
    echo "   uv를 설치합니다..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    success "uv 설치 완료"
    echo "   PATH 업데이트가 필요할 수 있습니다:"
    echo '   export PATH="$HOME/.cargo/bin:$PATH"'
fi
echo ""

# 6. poppler 설치 (PDF 처리용)
echo "6. poppler (PDF 도구) 설치 중..."
if brew list poppler &> /dev/null; then
    success "poppler가 이미 설치되어 있습니다"
else
    echo "   poppler를 설치합니다..."
    brew install poppler
    success "poppler 설치 완료"
fi
echo ""

# 7. Python 가상환경 설정
echo "7. Python 가상환경 설정 중..."
if [ -d ".venv" ]; then
    warning "가상환경이 이미 존재합니다. 재생성하시겠습니까? (y/n)"
    read -r response
    if [[ "$response" =~ ^[Yy]$ ]]; then
        rm -rf .venv
        uv venv .venv
        success "가상환경 재생성 완료"
    else
        success "기존 가상환경 유지"
    fi
else
    uv venv .venv
    success "가상환경 생성 완료"
fi
echo ""

# 8. Python 패키지 설치
echo "8. Python 패키지 설치 중..."
source .venv/bin/activate
uv pip install httpx pillow pdf2image
success "필요한 Python 패키지 설치 완료"
echo ""

# 9. 스크립트 실행 권한 설정
echo "9. 스크립트 실행 권한 설정 중..."
chmod +x setup_macos.sh 2>/dev/null || true
chmod +x start_server.sh 2>/dev/null || true
success "실행 권한 설정 완료"
echo ""

# 10. 디렉토리 구조 생성
echo "10. 디렉토리 구조 생성 중..."
mkdir -p models
mkdir -p data/test_images
mkdir -p logs
success "디렉토리 생성 완료"
echo ""

# 설치 완료 메시지
echo "=================================="
echo -e "${GREEN}설치가 완료되었습니다!${NC}"
echo "=================================="
echo ""
echo "다음 명령어로 OCR 서버를 시작할 수 있습니다:"
echo "  ./start_server.sh"
echo ""
echo "서버가 시작되면 다음 명령어로 테스트할 수 있습니다:"
echo "  source .venv/bin/activate"
echo "  python test_ocr.py"
echo ""
echo "자세한 사용법은 README.md를 참조하세요."