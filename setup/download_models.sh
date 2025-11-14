#!/bin/bash

# LightOnOCR 모델 다운로드 및 관리 스크립트
# 캐시된 모델을 프로젝트 models 폴더로 이동하거나 직접 다운로드

set -e

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

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

# 설정
MODELS_DIR="./models"
CACHE_DIR="$HOME/Library/Caches/llama.cpp"
HF_REPO="ggml-org/LightOnOCR-1B-1025-GGUF"

# 필수 파일 목록
declare -a REQUIRED_FILES=(
    "LightOnOCR-1B-1025-Q8_0.gguf"
    "mmproj-LightOnOCR-1B-1025-Q8_0.gguf"
)

# 옵션 파싱
MODE="copy"  # 기본값: 복사
VERIFY=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --copy)
            MODE="copy"
            shift
            ;;
        --symlink)
            MODE="symlink"
            shift
            ;;
        --download)
            MODE="download"
            shift
            ;;
        --verify)
            VERIFY=true
            shift
            ;;
        -h|--help)
            echo "사용법: $0 [옵션]"
            echo ""
            echo "옵션:"
            echo "  --copy      캐시에서 파일 복사 (기본값)"
            echo "  --symlink   심볼릭 링크 생성 (디스크 절약)"
            echo "  --download  Hugging Face에서 직접 다운로드"
            echo "  --verify    파일 무결성 검증"
            echo "  -h, --help  도움말 표시"
            exit 0
            ;;
        *)
            error "알 수 없는 옵션: $1"
            exit 1
            ;;
    esac
done

echo "=================================="
echo "LightOnOCR 모델 관리"
echo "=================================="
echo ""
echo "모드: $MODE"
echo "검증: $VERIFY"
echo ""

# models 디렉토리 생성
if [ ! -d "$MODELS_DIR" ]; then
    info "모델 디렉토리 생성 중..."
    mkdir -p "$MODELS_DIR"
    success "디렉토리 생성 완료: $MODELS_DIR"
else
    success "모델 디렉토리 존재: $MODELS_DIR"
fi
echo ""

# 파일 크기 확인 함수
get_file_size() {
    if [ -f "$1" ]; then
        du -h "$1" | cut -f1
    else
        echo "N/A"
    fi
}

# 각 필수 파일 처리
for FILE_NAME in "${REQUIRED_FILES[@]}"; do
    echo "📦 처리 중: $FILE_NAME"

    LOCAL_FILE="$MODELS_DIR/$FILE_NAME"
    CACHE_FILE="$CACHE_DIR/${HF_REPO//\//_}_$FILE_NAME"

    # 이미 로컬에 있는지 확인
    if [ -f "$LOCAL_FILE" ] || [ -L "$LOCAL_FILE" ]; then
        if [ -L "$LOCAL_FILE" ]; then
            success "심볼릭 링크 존재 ($(readlink "$LOCAL_FILE"))"
        else
            success "파일 존재 (크기: $(get_file_size "$LOCAL_FILE"))"
        fi
        continue
    fi

    # 모드별 처리
    case $MODE in
        copy|symlink)
            # 캐시 파일 확인
            if [ -f "$CACHE_FILE" ]; then
                info "캐시에서 발견: $CACHE_FILE"
                info "파일 크기: $(get_file_size "$CACHE_FILE")"

                if [ "$MODE" = "copy" ]; then
                    echo "   파일 복사 중..."
                    cp "$CACHE_FILE" "$LOCAL_FILE"
                    success "복사 완료"
                else
                    echo "   심볼릭 링크 생성 중..."
                    ln -s "$CACHE_FILE" "$LOCAL_FILE"
                    success "링크 생성 완료"
                fi
            else
                warning "캐시에 파일 없음"

                # huggingface-cli 확인
                if command -v huggingface-cli &> /dev/null; then
                    echo "   Hugging Face에서 다운로드 중..."
                    huggingface-cli download "$HF_REPO" "$FILE_NAME" \
                        --local-dir "$MODELS_DIR" \
                        --local-dir-use-symlinks False
                    success "다운로드 완료"
                else
                    error "huggingface-cli가 설치되지 않음"
                    echo "   다음 명령어로 설치하세요:"
                    echo "   source .venv/bin/activate && uv pip install huggingface-hub[cli]"
                    echo ""
                    echo "   또는 브라우저에서 직접 다운로드:"
                    echo "   https://huggingface.co/$HF_REPO/resolve/main/$FILE_NAME"
                    exit 1
                fi
            fi
            ;;

        download)
            info "직접 다운로드 모드"

            # huggingface-cli 확인
            if command -v huggingface-cli &> /dev/null; then
                echo "   Hugging Face에서 다운로드 중..."
                huggingface-cli download "$HF_REPO" "$FILE_NAME" \
                    --local-dir "$MODELS_DIR" \
                    --local-dir-use-symlinks False \
                    --force-download
                success "다운로드 완료"
            else
                # wget/curl fallback
                if command -v wget &> /dev/null; then
                    echo "   wget으로 다운로드 중..."
                    wget -O "$LOCAL_FILE" \
                        "https://huggingface.co/$HF_REPO/resolve/main/$FILE_NAME"
                    success "다운로드 완료"
                elif command -v curl &> /dev/null; then
                    echo "   curl로 다운로드 중..."
                    curl -L -o "$LOCAL_FILE" \
                        "https://huggingface.co/$HF_REPO/resolve/main/$FILE_NAME"
                    success "다운로드 완료"
                else
                    error "다운로드 도구 없음 (huggingface-cli, wget, curl)"
                    exit 1
                fi
            fi
            ;;
    esac

    echo ""
done

# 검증 (옵션)
if [ "$VERIFY" = true ]; then
    echo "🔍 파일 검증 중..."

    for FILE_NAME in "${REQUIRED_FILES[@]}"; do
        LOCAL_FILE="$MODELS_DIR/$FILE_NAME"

        if [ -f "$LOCAL_FILE" ] || [ -L "$LOCAL_FILE" ]; then
            # 실제 파일 경로 얻기
            if [ -L "$LOCAL_FILE" ]; then
                ACTUAL_FILE=$(readlink "$LOCAL_FILE")
            else
                ACTUAL_FILE="$LOCAL_FILE"
            fi

            # 파일 크기 확인
            FILE_SIZE=$(stat -f%z "$ACTUAL_FILE" 2>/dev/null || stat -c%s "$ACTUAL_FILE" 2>/dev/null)

            # 최소 크기 체크 (100MB 이상)
            if [ "$FILE_SIZE" -gt 104857600 ]; then
                success "$FILE_NAME: $(get_file_size "$ACTUAL_FILE")"
            else
                error "$FILE_NAME: 파일 크기가 너무 작음 ($(get_file_size "$ACTUAL_FILE"))"
            fi
        else
            error "$FILE_NAME: 파일 없음"
        fi
    done
    echo ""
fi

# 최종 상태 출력
echo "=================================="
echo "📊 최종 상태"
echo "=================================="
echo ""
echo "모델 디렉토리: $MODELS_DIR"
echo ""

for FILE_NAME in "${REQUIRED_FILES[@]}"; do
    LOCAL_FILE="$MODELS_DIR/$FILE_NAME"

    if [ -L "$LOCAL_FILE" ]; then
        echo "$FILE_NAME"
        echo "   타입: 심볼릭 링크"
        echo "   대상: $(readlink "$LOCAL_FILE")"
        echo "   크기: $(get_file_size "$(readlink "$LOCAL_FILE")")"
    elif [ -f "$LOCAL_FILE" ]; then
        echo "$FILE_NAME"
        echo "   타입: 일반 파일"
        echo "   크기: $(get_file_size "$LOCAL_FILE")"
    else
        echo "$FILE_NAME"
        echo "   상태: 없음"
    fi
    echo ""
done

# 디스크 사용량
TOTAL_SIZE=$(du -sh "$MODELS_DIR" 2>/dev/null | cut -f1)
echo "총 디스크 사용량: $TOTAL_SIZE"
echo ""

echo "모델 준비 완료!"
echo "   이제 ./start_server.sh를 실행할 수 있습니다."