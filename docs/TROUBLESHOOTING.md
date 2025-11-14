# 문제 해결 가이드

LightOnOCR 사용 중 발생할 수 있는 문제와 해결 방법을 설명합니다.

## 🚨 자주 발생하는 문제

### 1. 서버가 시작되지 않음

#### 증상
```
Error: Address already in use
```

#### 해결 방법
```bash
# 포트 사용 확인
lsof -i :8080

# 프로세스 종료
kill $(lsof -t -i:8080)

# 다시 시작
./start_server.sh
```

#### 다른 포트 사용
```bash
# start_server.sh 수정
PORT=8090  # 다른 포트로 변경
```

### 2. 모델 다운로드 실패

#### 증상
```
Failed to download model from Hugging Face
```

#### 해결 방법
```bash
# 수동 다운로드
llama-cli -hf ggml-org/LightOnOCR-1B-1025-GGUF --help

# 캐시 삭제 후 재시도
rm -rf ~/.cache/huggingface
./start_server.sh
```

### 3. Python 패키지 설치 실패

#### 증상
```
ERROR: Could not find a version that satisfies the requirement
```

#### 해결 방법
```bash
# 가상환경 재생성
rm -rf .venv
uv venv .venv
source .venv/bin/activate

# 패키지 재설치
uv pip install -r requirements.txt

# 개별 설치
uv pip install httpx
uv pip install pillow
uv pip install pdf2image
uv pip install pyyaml
```

### 4. OCR 처리 중 오류

#### 증상: "can't have unbuffered text I/O"
```python
# 이미 수정됨 - 최신 버전 확인
git pull
```

#### 증상: API 오류
```
❌ API 오류: 500
```

#### 해결 방법
```bash
# 서버 재시작
kill $(lsof -t -i:8080)
./start_server.sh

# 서버 로그 확인
./start_server.sh 2>&1 | tee server.log
```

## 💻 시스템별 문제

### macOS Apple Silicon

#### MPS 가속이 작동하지 않음

```bash
# Metal 지원 확인
system_profiler SPDisplaysDataType | grep Metal

# CPU 모드로 전환
# start_server.sh에서
GPU_LAYERS=0  # GPU 사용 안 함
```

#### 메모리 부족

```bash
# GPU 레이어 수 감소
GPU_LAYERS=50  # 999에서 감소

# 컨텍스트 크기 감소
CONTEXT_SIZE=4096  # 8192에서 감소
```

### macOS Intel

#### 느린 처리 속도

Intel Mac에서는 GPU 가속이 제한적입니다:

```bash
# CPU 최적화
THREADS=8  # CPU 코어 수에 맞게 조정
GPU_LAYERS=0  # CPU 모드
```

## 📄 PDF 처리 문제

### poppler 설치 문제

#### 증상
```
pdf2image.exceptions.PDFInfoNotInstalledError
```

#### 해결 방법
```bash
# Homebrew로 설치
brew install poppler

# 경로 확인
which pdfinfo
which pdftoppm

# 경로 설정 (필요시)
export PATH="/opt/homebrew/bin:$PATH"
```

### PDF 페이지 처리 실패

#### 반복 패턴 감지

```yaml
# ocr_config.yml
advanced:
  repetition_detection:
    enabled: false  # 비활성화
```

#### 타임아웃 오류

```bash
# 타임아웃 증가
python ocr.py --page-timeout 180 document.pdf

# 또는 설정 파일에서
pdf:
  page_timeout: 180.0
```

### 대용량 PDF 처리

#### 메모리 오류

```bash
# 페이지 단위로 처리
python ocr.py \
    --start-page 1 \
    --end-page 50 \
    large_document.pdf

# 이어서 처리
python ocr.py \
    --start-page 51 \
    --end-page 100 \
    large_document.pdf
```

## 🖼️ 이미지 처리 문제

### 텍스트 인식 불량

#### 이미지 품질 개선

```python
from PIL import Image, ImageEnhance

# 이미지 전처리
img = Image.open("blurry.jpg")

# 대비 향상
enhancer = ImageEnhance.Contrast(img)
img = enhancer.enhance(2.0)

# 크기 확대
width, height = img.size
img = img.resize((width*2, height*2), Image.Resampling.LANCZOS)

img.save("enhanced.jpg")
```

### 특수 문자 인식 문제

#### 프롬프트 조정

```python
# ocr.py 수정 또는 커스텀 스크립트
prompt = """
Extract all text including special characters,
mathematical symbols, and non-English characters.
Preserve exact formatting.
"""
```

## 🔧 설정 파일 문제

### YAML 파싱 오류

#### 증상
```
yaml.scanner.ScannerError: mapping values are not allowed here
```

#### 해결 방법
```yaml
# 올바른 들여쓰기 확인 (공백 2개)
ocr:
  streaming: true  # ✓ 올바름
   streaming: true  # ✗ 잘못된 들여쓰기
```

### 설정이 적용되지 않음

```bash
# 설정 파일 경로 확인
python ocr.py -c ./ocr_config.yml document.pdf

# 설정 무시하고 실행
python ocr.py --no-config document.pdf
```

## 🌐 네트워크 문제

### 연결 거부

#### 증상
```
httpx.ConnectError: [Errno 61] Connection refused
```

#### 해결 방법
```bash
# 서버 상태 확인
ps aux | grep llama-server

# 서버 시작
./start_server.sh

# 포트 확인
netstat -an | grep 8080
```

### 타임아웃

```python
# 타임아웃 증가
import httpx

client = httpx.Client(timeout=300.0)  # 5분
```

## 📊 성능 문제

### 처리 속도가 느림

1. **GPU 가속 확인**
```bash
# 서버 로그에서 확인
./start_server.sh | grep -i "metal\|mps\|gpu"
```

2. **이미지 크기 최적화**
```python
# 큰 이미지 리사이즈
from PIL import Image

img = Image.open("huge_image.jpg")
img.thumbnail((2048, 2048), Image.Resampling.LANCZOS)
img.save("optimized.jpg")
```

3. **배치 크기 조정**
```bash
# 한 번에 처리할 페이지 수 제한
python ocr.py --batch-size 10 document.pdf
```

## 🔍 디버깅

### 상세 로그 활성화

```bash
# 환경 변수 설정
export DEBUG=1
export VERBOSE=1

# 로그 파일로 저장
python ocr.py document.pdf 2>&1 | tee debug.log
```

### 서버 로그 분석

```bash
# 실시간 로그 모니터링
tail -f server.log

# 오류만 필터링
grep -i error server.log

# 경고 확인
grep -i warning server.log
```

### Python 디버깅

```python
# 디버그 모드 실행
python -m pdb ocr.py document.pdf

# 브레이크포인트 설정
import pdb; pdb.set_trace()
```

## 📞 지원 받기

### 로그 수집

문제 보고 시 다음 정보를 포함하세요:

```bash
# 시스템 정보
uname -a
python --version
pip list

# 서버 로그
tail -n 100 server.log

# OCR 로그
python ocr.py --debug document.pdf 2>&1 | tee ocr_debug.log
```

### GitHub Issues

1. 문제 재현 단계
2. 에러 메시지 전체
3. 시스템 환경
4. 사용한 명령어

## 🔄 초기화 및 재설치

모든 방법이 실패한 경우:

```bash
# 1. 백업
cp -r lightonocr_test lightonocr_backup

# 2. 클린 설치
rm -rf ~/.cache/huggingface
rm -rf .venv
rm -rf build

# 3. 재설치
./setup/setup_macos.sh

# 4. 테스트
./start_server.sh
python ocr.py data/sample.png
```