#!/bin/bash

# 모델 상태 확인 유틸리티
# 로컬 및 캐시 모델 파일 상태를 진단합니다

set -e

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# 설정
MODELS_DIR="./models"
CACHE_DIR="$HOME/Library/Caches/llama.cpp"
HF_REPO="ggml-org/LightOnOCR-1B-1025-GGUF"

# 필수 파일
MAIN_MODEL="LightOnOCR-1B-1025-Q8_0.gguf"
MMPROJ_MODEL="mmproj-LightOnOCR-1B-1025-Q8_0.gguf"

# 함수 정의
success() {
    echo -e "${GREEN}✓${NC} $1"
}

warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

error() {
    echo -e "${RED}✗${NC} $1"
}

info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

# 파일 크기 얻기 (휴먼 리더블)
get_file_size() {
    if [ -f "$1" ] || [ -L "$1" ]; then
        du -h "$1" 2>/dev/null | cut -f1
    else
        echo "N/A"
    fi
}

# 파일 크기 얻기 (바이트)
get_file_size_bytes() {
    if [ -f "$1" ] || [ -L "$1" ]; then
        stat -f%z "$1" 2>/dev/null || stat -c%s "$1" 2>/dev/null || echo "0"
    else
        echo "0"
    fi
}

echo "=================================="
echo -e "${CYAN}🔍 LightOnOCR 모델 상태 확인${NC}"
echo "=================================="
echo ""
echo "검사 시간: $(date "+%Y-%m-%d %H:%M:%S")"
echo ""

# 로컬 모델 확인
echo -e "${BLUE}📁 로컬 모델 디렉토리${NC}"
echo "   경로: $MODELS_DIR"
echo ""

LOCAL_SIZE_TOTAL=0

# 메인 모델 확인
LOCAL_MAIN="$MODELS_DIR/$MAIN_MODEL"
if [ -L "$LOCAL_MAIN" ]; then
    LINK_TARGET=$(readlink "$LOCAL_MAIN")
    success "$MAIN_MODEL"
    echo "   타입: 심볼릭 링크"
    echo "   대상: $LINK_TARGET"
    echo "   크기: $(get_file_size "$LINK_TARGET")"
    LOCAL_SIZE_TOTAL=$((LOCAL_SIZE_TOTAL + $(get_file_size_bytes "$LINK_TARGET")))
elif [ -f "$LOCAL_MAIN" ]; then
    success "$MAIN_MODEL"
    echo "   타입: 일반 파일"
    echo "   크기: $(get_file_size "$LOCAL_MAIN")"
    echo "   수정: $(stat -f "%Sm" -t "%Y-%m-%d %H:%M" "$LOCAL_MAIN" 2>/dev/null || date -r "$LOCAL_MAIN" "+%Y-%m-%d %H:%M" 2>/dev/null)"
    LOCAL_SIZE_TOTAL=$((LOCAL_SIZE_TOTAL + $(get_file_size_bytes "$LOCAL_MAIN")))
else
    error "$MAIN_MODEL - 파일 없음"
fi
echo ""

# 프로젝션 모델 확인
LOCAL_MMPROJ="$MODELS_DIR/$MMPROJ_MODEL"
if [ -L "$LOCAL_MMPROJ" ]; then
    LINK_TARGET=$(readlink "$LOCAL_MMPROJ")
    success "$MMPROJ_MODEL"
    echo "   타입: 심볼릭 링크"
    echo "   대상: $LINK_TARGET"
    echo "   크기: $(get_file_size "$LINK_TARGET")"
    LOCAL_SIZE_TOTAL=$((LOCAL_SIZE_TOTAL + $(get_file_size_bytes "$LINK_TARGET")))
elif [ -f "$LOCAL_MMPROJ" ]; then
    success "$MMPROJ_MODEL"
    echo "   타입: 일반 파일"
    echo "   크기: $(get_file_size "$LOCAL_MMPROJ")"
    echo "   수정: $(stat -f "%Sm" -t "%Y-%m-%d %H:%M" "$LOCAL_MMPROJ" 2>/dev/null || date -r "$LOCAL_MMPROJ" "+%Y-%m-%d %H:%M" 2>/dev/null)"
    LOCAL_SIZE_TOTAL=$((LOCAL_SIZE_TOTAL + $(get_file_size_bytes "$LOCAL_MMPROJ")))
else
    error "$MMPROJ_MODEL - 파일 없음"
fi
echo ""

# 캐시 확인
echo -e "${BLUE}💾 캐시 상태${NC}"
echo "   경로: $CACHE_DIR"
echo ""

CACHE_SIZE_TOTAL=0
CACHE_EXISTS=false

# 캐시 디렉토리 존재 확인
if [ -d "$CACHE_DIR" ]; then
    # 캐시 파일 확인
    CACHE_MAIN="$CACHE_DIR/${HF_REPO//\//_}_$MAIN_MODEL"
    CACHE_MMPROJ="$CACHE_DIR/${HF_REPO//\//_}_$MMPROJ_MODEL"

    if [ -f "$CACHE_MAIN" ]; then
        info "메인 모델 캐시: $(get_file_size "$CACHE_MAIN")"
        CACHE_SIZE_TOTAL=$((CACHE_SIZE_TOTAL + $(get_file_size_bytes "$CACHE_MAIN")))
        CACHE_EXISTS=true
    fi

    if [ -f "$CACHE_MMPROJ" ]; then
        info "프로젝션 캐시: $(get_file_size "$CACHE_MMPROJ")"
        CACHE_SIZE_TOTAL=$((CACHE_SIZE_TOTAL + $(get_file_size_bytes "$CACHE_MMPROJ")))
        CACHE_EXISTS=true
    fi

    if [ "$CACHE_EXISTS" = false ]; then
        info "캐시 파일 없음"
    fi
else
    warning "캐시 디렉토리 없음"
fi
echo ""

# 디스크 사용량 요약
echo -e "${BLUE}📊 디스크 사용량${NC}"
echo ""

# 로컬 크기 계산
LOCAL_SIZE_MB=$((LOCAL_SIZE_TOTAL / 1024 / 1024))
echo "   로컬 모델: ${LOCAL_SIZE_MB}MB"

# 캐시 크기 계산
if [ "$CACHE_EXISTS" = true ]; then
    CACHE_SIZE_MB=$((CACHE_SIZE_TOTAL / 1024 / 1024))
    echo "   캐시: ${CACHE_SIZE_MB}MB"

    # 중복 확인
    if [ "$LOCAL_SIZE_TOTAL" -gt 0 ] && [ "$CACHE_SIZE_TOTAL" -gt 0 ]; then
        TOTAL_SIZE_MB=$(((LOCAL_SIZE_TOTAL + CACHE_SIZE_TOTAL) / 1024 / 1024))
        warning "중복 저장: 총 ${TOTAL_SIZE_MB}MB 사용 중"
        echo ""
        echo "   💡 디스크 절약을 위해 다음을 고려하세요:"
        echo "      ./download_models.sh --symlink"
    fi
else
    echo "   캐시: 0MB"
fi
echo ""

# 서버 실행 가능 여부
echo -e "${BLUE}🚀 서버 실행 준비 상태${NC}"
echo ""

CAN_RUN=true

# llama-server 확인
if command -v llama-server &> /dev/null; then
    success "llama-server 설치됨"
    LLAMA_VERSION=$(llama-cli --version 2>/dev/null | head -1)
    echo "   버전: $LLAMA_VERSION"
else
    error "llama-server 없음"
    CAN_RUN=false
fi

# 모델 파일 확인
if [ -f "$LOCAL_MAIN" ] || [ -L "$LOCAL_MAIN" ]; then
    success "메인 모델 준비됨"
else
    error "메인 모델 없음"
    CAN_RUN=false
fi

if [ -f "$LOCAL_MMPROJ" ] || [ -L "$LOCAL_MMPROJ" ]; then
    success "프로젝션 모델 준비됨"
else
    warning "프로젝션 모델 없음 (OCR 제한됨)"
fi

echo ""

# 최종 상태
if [ "$CAN_RUN" = true ]; then
    echo -e "${GREEN}서버 실행 가능${NC}"
    echo "   ./start_server.sh를 실행하세요"
else
    echo -e "${RED}서버 실행 불가${NC}"
    echo ""
    echo "   해결 방법:"

    if [ ! -f "$LOCAL_MAIN" ] && [ ! -L "$LOCAL_MAIN" ]; then
        echo "   1. 모델 다운로드: ./download_models.sh"
    fi

    if ! command -v llama-server &> /dev/null; then
        echo "   2. llama.cpp 설치: brew install llama.cpp"
    fi
fi
echo ""

# 권장 사항
echo -e "${BLUE}💡 권장 사항${NC}"
echo ""

# 모델 없을 때
if [ ! -f "$LOCAL_MAIN" ] && [ ! -L "$LOCAL_MAIN" ]; then
    echo "• 모델을 다운로드하세요:"
    echo "  ./download_models.sh"
    echo ""
fi

# 중복 파일 있을 때
if [ "$CACHE_EXISTS" = true ] && [ "$LOCAL_SIZE_TOTAL" -gt 0 ]; then
    # 심볼릭 링크 확인
    if [ ! -L "$LOCAL_MAIN" ]; then
        echo "• 디스크 공간 절약을 위해 심볼릭 링크 사용:"
        echo "  rm -rf models/*.gguf"
        echo "  ./download_models.sh --symlink"
        echo ""
    fi
fi

# llama.cpp 버전 문제 경고
if command -v llama-server &> /dev/null; then
    if [[ "$LLAMA_VERSION" == *"5921"* ]]; then
        warning "현재 llama.cpp 버전이 LightOnOCR을 지원하지 않을 수 있습니다"
        echo "   PR #16764 병합 대기 중"
        echo ""
    fi
fi

echo "=================================="