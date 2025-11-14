#!/bin/bash

# LightOnOCR-1B GGUF 모델로 llama-server 시작
# MPS 가속을 활용하여 Apple Silicon에서 최적 성능

echo "Starting LightOnOCR-1B server..."
echo "Model: ggml-org/LightOnOCR-1B-1025-GGUF"
echo "Context size: 8192"
echo "Server will be available at http://localhost:8080"
echo ""

# llama-server 실행
# -hf: Hugging Face 모델 직접 로드
# -c: 컨텍스트 크기
# --n-gpu-layers: GPU 레이어 수 (MPS 가속)
llama-server \
    -hf ggml-org/LightOnOCR-1B-1025-GGUF \
    -c 8192 \
    --n-gpu-layers 999 \
    --host 0.0.0.0 \
    --port 8080