# 고급 설정 가이드

LightOnOCR의 고급 기능과 최적화 방법을 설명합니다.

## 서버 설정

### 포트 변경

`start_server.sh` 파일 수정:

```bash
#!/bin/bash

# 포트 설정
PORT=8080  # 원하는 포트로 변경

# GPU 레이어 설정
GPU_LAYERS=999  # MPS 가속 사용

# 컨텍스트 크기
CONTEXT_SIZE=8192  # 필요시 증가

# 모델 경로
MODEL="ggml-org/LightOnOCR-1B-1025-GGUF"

# 서버 실행
llama-server \
    --hf "$MODEL" \
    --port $PORT \
    --ctx-size $CONTEXT_SIZE \
    --threads 8 \
    --gpu-layers $GPU_LAYERS
```

### GPU 메모리 최적화

메모리가 부족한 경우:

```bash
# GPU 레이어 수 조정
GPU_LAYERS=50  # 999 대신 더 작은 값 사용

# 또는 CPU 모드로 실행
GPU_LAYERS=0  # GPU 사용 안 함
```

### 컨텍스트 크기 조정

더 긴 텍스트 처리:

```bash
# 컨텍스트 크기 증가 (메모리 사용량 증가)
CONTEXT_SIZE=16384  # 기본 8192에서 증가
CONTEXT_SIZE=32768  # 매우 긴 문서용
```

## PDF 처리 최적화

### 대용량 PDF 처리

```python
# 메모리 효율적인 처리
python ocr.py \
    --skip-errors \           # 오류 페이지 건너뛰기
    --page-timeout 60 \       # 페이지 타임아웃 단축
    --max-page-tokens 4000 \  # 토큰 제한
    --save-mode line \        # 줄 단위 저장
    large_document.pdf
```

### 병렬 처리 (스크립트)

```python
#!/usr/bin/env python3
import concurrent.futures
import subprocess
from pathlib import Path

def process_pdf_range(pdf_path, start, end):
    """특정 범위의 페이지만 처리"""
    cmd = [
        "python", "ocr.py",
        "--start-page", str(start),
        "--end-page", str(end),
        "--quiet",
        str(pdf_path)
    ]
    subprocess.run(cmd)
    return f"Pages {start}-{end} completed"

def parallel_pdf_ocr(pdf_path, num_workers=4):
    """PDF를 여러 워커로 병렬 처리"""
    # PDF 페이지 수 확인 (PyPDF2 필요)
    from PyPDF2 import PdfReader
    reader = PdfReader(pdf_path)
    total_pages = len(reader.pages)

    # 페이지 범위 분할
    pages_per_worker = total_pages // num_workers
    ranges = []
    for i in range(num_workers):
        start = i * pages_per_worker + 1
        end = start + pages_per_worker - 1
        if i == num_workers - 1:
            end = total_pages
        ranges.append((start, end))

    # 병렬 처리
    with concurrent.futures.ThreadPoolExecutor(max_workers=num_workers) as executor:
        futures = []
        for start, end in ranges:
            future = executor.submit(process_pdf_range, pdf_path, start, end)
            futures.append(future)

        for future in concurrent.futures.as_completed(futures):
            print(future.result())

if __name__ == "__main__":
    parallel_pdf_ocr("large_document.pdf", num_workers=4)
```

## 이미지 전처리

### 이미지 품질 개선

```python
from PIL import Image, ImageEnhance, ImageFilter

def preprocess_image(image_path):
    """OCR 정확도를 위한 이미지 전처리"""
    img = Image.open(image_path)

    # 그레이스케일 변환
    img = img.convert('L')

    # 대비 향상
    enhancer = ImageEnhance.Contrast(img)
    img = enhancer.enhance(2.0)

    # 선명도 향상
    img = img.filter(ImageFilter.SHARPEN)

    # 크기 조정 (너무 작은 텍스트 방지)
    width, height = img.size
    if width < 1000:
        ratio = 1000 / width
        new_size = (1000, int(height * ratio))
        img = img.resize(new_size, Image.Resampling.LANCZOS)

    # 저장
    processed_path = image_path.replace('.', '_processed.')
    img.save(processed_path, quality=95)

    return processed_path
```

### 배치 이미지 처리

```bash
#!/bin/bash
# 폴더의 모든 이미지 처리

for file in images/*.{jpg,png,jpeg}; do
    if [ -f "$file" ]; then
        echo "Processing $file..."
        python ocr.py --quiet "$file"
    fi
done
```

## 반복 패턴 감지 튜닝

### 설정 조정

```yaml
# ocr_config.yml
advanced:
  repetition_detection:
    enabled: true
    window_size: 30      # 작게 설정 (빠른 감지)
    threshold: 0.9       # 높게 설정 (엄격한 판정)
    max_normal_reps: 3   # 낮게 설정 (빠른 중단)
```

### 비활성화

반복이 정상적인 문서의 경우:

```yaml
advanced:
  repetition_detection:
    enabled: false  # 반복 감지 비활성화
```

## 로깅 및 디버깅

### 디버그 모드 활성화

```yaml
# ocr_config.yml
debug:
  enabled: true
  log_api_calls: true
```

### 상세 로그 출력

```python
# 커스텀 로깅 추가
import logging

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    filename='ocr_debug.log'
)

# ocr.py 실행
python ocr.py --stats --verbose document.pdf
```

## 성능 모니터링

### 시스템 리소스 모니터링

```bash
# 실시간 GPU 사용량 확인 (macOS)
sudo powermetrics --samplers gpu_power -i 1000

# 메모리 사용량 확인
while true; do
    ps aux | grep llama-server | grep -v grep
    sleep 2
done
```

### 처리 통계 분석

```python
# 통계 수집 스크립트
import json
from datetime import datetime

def analyze_stats(log_file):
    """OCR 처리 통계 분석"""
    stats = {
        'total_pages': 0,
        'successful_pages': 0,
        'failed_pages': 0,
        'total_tokens': 0,
        'total_time': 0,
        'avg_page_time': 0
    }

    with open(log_file, 'r') as f:
        for line in f:
            # 로그 파싱 및 통계 수집
            pass

    # 결과 출력
    print(json.dumps(stats, indent=2))

    # CSV 저장
    with open('ocr_stats.csv', 'a') as f:
        f.write(f"{datetime.now()},{stats['total_pages']},{stats['avg_page_time']}\n")
```

## 커스터마이징

### 프롬프트 수정

```python
# ocr.py 수정
def perform_ocr(image_base64, prompt=None, ...):
    if prompt is None:
        # 커스텀 프롬프트
        prompt = """
        Extract all text from this image.
        Preserve the original formatting and structure.
        Include all headers, paragraphs, and lists.
        """

    request_data = {
        "messages": [{
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                # ...
            ]
        }]
    }
```

### 후처리 추가

```python
def post_process_text(text):
    """OCR 결과 후처리"""
    import re

    # 불필요한 공백 제거
    text = re.sub(r'\n{3,}', '\n\n', text)

    # 구두점 정리
    text = re.sub(r'\s+([.,;!?])', r'\1', text)

    # 줄 끝 공백 제거
    lines = [line.rstrip() for line in text.split('\n')]
    text = '\n'.join(lines)

    return text
```

## 배포 고려사항

### Docker 컨테이너화

```dockerfile
# Dockerfile
FROM python:3.12-slim

# 의존성 설치
RUN apt-get update && apt-get install -y \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

# 앱 복사
WORKDIR /app
COPY . .

# Python 패키지 설치
RUN pip install -r requirements.txt

# 실행
CMD ["python", "ocr.py"]
```

### systemd 서비스

```ini
# /etc/systemd/system/lightonocr.service
[Unit]
Description=LightOnOCR Server
After=network.target

[Service]
Type=simple
User=ocr
WorkingDirectory=/opt/lightonocr
ExecStart=/opt/lightonocr/start_server.sh
Restart=always

[Install]
WantedBy=multi-user.target
```

## 보안 고려사항

### API 인증 추가

```python
# 간단한 API 키 인증
API_KEY = "your-secret-key"

def verify_api_key(request_headers):
    auth_header = request_headers.get("Authorization")
    if auth_header != f"Bearer {API_KEY}":
        raise ValueError("Invalid API key")
```

### 네트워크 제한

```bash
# 로컬호스트만 허용
llama-server --host 127.0.0.1 --port 8080

# 특정 IP만 허용 (방화벽 설정)
sudo pfctl -e
echo "pass in proto tcp from 192.168.1.0/24 to any port 8080" | sudo pfctl -f -
```