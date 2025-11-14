# 설정 가이드

LightOnOCR의 설정 파일 구조와 고급 옵션을 설명합니다.

## 목차

1. [설정 파일 생성](#설정-파일-생성)
2. [설정 파일 구조](#설정-파일-구조)
3. [저장 모드](#저장-모드)
4. [설정 우선순위](#설정-우선순위)
5. [서버 설정](#서버-설정)
6. [PDF 처리 최적화](#pdf-처리-최적화)
7. [반복 패턴 감지](#반복-패턴-감지)
8. [디버깅](#디버깅)

---

## 설정 파일 생성

```bash
# 기본 설정 파일 생성
python ocr.py --create-config ocr_config.yml

# 특정 위치에 생성
python ocr.py --create-config ~/.config/lightonocr/config.yml
```

### 자동 탐색 위치

1. `./ocr_config.yml`
2. `./ocr_config.yaml`
3. `./.ocr_config.yml`
4. `./.ocr_config.yaml`
5. `~/.config/lightonocr/config.yml`

---

## 설정 파일 구조

```yaml
# 서버 설정
server:
  url: "http://localhost:8080"  # 서버 URL
  model: "LightOnOCR-1B-1025"    # 모델 이름
  timeout: 120                   # 요청 타임아웃 (초)

# OCR 처리 설정
ocr:
  streaming: true                # 스트리밍 모드 (true/false)
  save_mode: "token"             # 저장 모드 (token/word/sentence/paragraph/line)
  save_file: true                # 파일 저장 여부
  quiet: false                   # 조용한 모드
  show_stats: false              # 처리 통계 표시

# PDF 처리 설정
pdf:
  skip_errors: false             # 오류 발생 시 건너뛰기
  max_retries: 2                 # 페이지당 최대 재시도 횟수
  page_timeout: 120.0            # 페이지당 최대 처리 시간 (초)
  max_page_tokens: 8000          # 페이지당 최대 토큰 수
  dpi: 200                       # PDF를 이미지로 변환할 때 DPI

# 이미지 처리 설정
image:
  jpeg_quality: 95               # JPEG 변환 품질 (1-100)
  supported_formats:             # 지원 이미지 형식
    - ".png"
    - ".jpg"
    - ".jpeg"
    - ".bmp"
    - ".gif"
    - ".tiff"

# 고급 설정
advanced:
  repetition_detection:
    enabled: true                # 반복 패턴 감지 활성화
    window_size: 50              # 비교할 토큰 윈도우 크기
    threshold: 0.8               # 반복 판정 유사도 (0.0-1.0)
    max_normal_reps: 5           # 정상 반복 최대 횟수
  api:
    temperature: 0.1             # 텍스트 생성 온도 (낮을수록 일관성)
    max_tokens: 4096             # 최대 생성 토큰 수

# 출력 형식 설정
output:
  include_headers: true          # 마크다운 헤더 포함
  include_separators: true       # 페이지 구분자 포함
  include_timing: true           # 처리 시간 정보 포함

# 디버그 설정
debug:
  enabled: false                 # 디버그 모드
  log_api_calls: false           # API 요청/응답 로깅
```

---

## 저장 모드

### token (기본값)
- 매 토큰마다 즉시 파일에 저장
- 가장 안정적이지만 I/O가 많음
- 중간에 중단되어도 데이터 손실 최소

### word
- 단어 단위로 저장
- 공백이나 줄바꿈이 나올 때마다 저장

### sentence
- 문장 단위로 저장
- 마침표, 느낌표, 물음표가 나올 때 저장

### paragraph
- 문단 단위로 저장
- 연속된 줄바꿈이 나올 때 저장

### line
- 줄 단위로 저장
- 줄바꿈이 나올 때마다 저장

---

## 설정 우선순위

1. **명령줄 인자** (최우선)
2. **YAML 설정 파일**
3. **기본값**

### 예시

```bash
# config.yml: quiet: true
# 명령줄이 우선시됨 (quiet 모드 비활성화)
python ocr.py -c config.yml --no-quiet document.pdf

# 설정 파일 무시하고 기본값으로 실행
python ocr.py --no-config document.pdf

# 설정 파일 사용하면서 특정 옵션만 덮어쓰기
python ocr.py -c stable_config.yml --quiet --skip-errors document.pdf
```

---

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

---

## PDF 처리 최적화

### 빠른 처리용 설정

```yaml
# fast_config.yml
ocr:
  streaming: false
  save_mode: "paragraph"
  quiet: true
  show_stats: false

pdf:
  skip_errors: true
  max_retries: 1
  page_timeout: 60.0
```

### 안정성 우선 설정

```yaml
# stable_config.yml
ocr:
  streaming: true
  save_mode: "token"
  quiet: false
  show_stats: true

pdf:
  skip_errors: false
  max_retries: 3
  page_timeout: 180.0
  max_page_tokens: 10000
```

### 대용량 PDF용 설정

```yaml
# large_pdf_config.yml
ocr:
  streaming: true
  save_mode: "line"
  quiet: true
  show_stats: false

pdf:
  skip_errors: true
  max_retries: 1
  page_timeout: 90.0
  max_page_tokens: 5000

advanced:
  repetition_detection:
    enabled: true
    max_normal_reps: 3
```

### 명령줄 최적화

```bash
# 메모리 효율적인 처리
python ocr.py \
    --skip-errors \           # 오류 페이지 건너뛰기
    --page-timeout 60 \       # 페이지 타임아웃 단축
    --max-page-tokens 4000 \  # 토큰 제한
    --save-mode line \        # 줄 단위 저장
    large_document.pdf
```

---

## 반복 패턴 감지

### 기본 설정

```yaml
advanced:
  repetition_detection:
    enabled: true
    window_size: 50      # 비교할 토큰 윈도우 크기
    threshold: 0.8       # 반복 판정 유사도
    max_normal_reps: 5   # 정상 반복 최대 횟수
```

### 엄격한 감지

```yaml
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

---

## 디버깅

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

---

## 환경별 설정 관리

```bash
# 개발 환경
python ocr.py -c configs/dev.yml document.pdf

# 프로덕션 환경
python ocr.py -c configs/prod.yml document.pdf

# 테스트 환경
python ocr.py -c configs/test.yml document.pdf
```
