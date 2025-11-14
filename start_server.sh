#!/bin/bash

# LightOnOCR llama-server 시작 스크립트

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 로고 출력
echo -e "${BLUE}"
echo "╔═══════════════════════════════════════╗"
echo "║        LightOnOCR Server v1.0         ║"
echo "║     Powered by llama.cpp & MPS        ║"
echo "╚═══════════════════════════════════════╝"
echo -e "${NC}"

# 설정
MODEL="ggml-org/LightOnOCR-1B-1025-GGUF"
CONTEXT_SIZE=8192
GPU_LAYERS=999  # 모든 레이어를 GPU(MPS)로
HOST="0.0.0.0"
PORT=8080
THREADS=-1  # 자동 감지

echo "🔧 서버 설정:"
echo "   모델: $MODEL"
echo "   컨텍스트: $CONTEXT_SIZE 토큰"
echo "   GPU 레이어: $GPU_LAYERS (MPS 가속)"
echo "   주소: http://$HOST:$PORT"
echo ""

# llama-server 존재 확인
if ! command -v llama-server &> /dev/null; then
    echo -e "${RED}✗ llama-server를 찾을 수 없습니다${NC}"
    echo "  ./setup_macos.sh를 먼저 실행해주세요"
    exit 1
fi

# 이미 실행 중인 서버 확인
if lsof -i :$PORT &> /dev/null; then
    echo -e "${YELLOW}⚠ 포트 $PORT가 이미 사용 중입니다${NC}"
    echo "  기존 서버를 종료하거나 다른 포트를 사용하세요"
    echo "  기존 프로세스 종료: kill \$(lsof -t -i:$PORT)"
    exit 1
fi

echo -e "${GREEN}🚀 서버를 시작합니다...${NC}"
echo "   모델 다운로드가 필요한 경우 시간이 걸릴 수 있습니다 (약 2GB)"
echo ""
echo "📝 사용법:"
echo "   1. 웹 UI: http://localhost:$PORT"
echo "   2. API 테스트: python test_ocr.py"
echo "   3. 종료: Ctrl+C"
echo ""
echo "========================================="
echo ""

# 로그 디렉토리 생성
mkdir -p logs

# 현재 시간으로 로그 파일명 생성
LOG_FILE="logs/llama_server_$(date +%Y%m%d_%H%M%S).log"

echo "📄 로그 파일: $LOG_FILE"
echo ""

# llama-server 실행
# -hf: Hugging Face 모델 직접 로드
# -c: 컨텍스트 크기
# -ngl: GPU 레이어 수 (MPS 가속)
# --host: 바인드 주소
# --port: 포트
# -t: 스레드 수
exec llama-server \
    -hf "$MODEL" \
    -c $CONTEXT_SIZE \
    -ngl $GPU_LAYERS \
    --host $HOST \
    --port $PORT \
    -t $THREADS \
    2>&1 | tee "$LOG_FILE"