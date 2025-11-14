# LightOnOCR - 맥에서 돌아가는 OCR

이미지와 PDF에서 텍스트를 추출하는 로컬 OCR 서버입니다.
Apple Silicon의 GPU를 활용해 빠르게 동작합니다.

## 빠른 시작

### 1. 설치 (5분)

```bash
# 프로젝트 다운로드
git clone https://github.com/yourusername/lightonocr_test.git
cd lightonocr_test

# 자동 설치 (처음 한 번만)
./setup/setup_macos.sh

# 서버 실행
./start_server.sh
```

첫 실행 시 모델 다운로드로 5-10분이 소요됩니다 (약 2GB).

### 2. OCR 실행

```bash
# 가상환경 활성화
source .venv/bin/activate

# 이미지 OCR
python ocr.py image.png

# PDF OCR
python ocr.py document.pdf
```

결과는 자동으로 `.md` 파일로 저장됩니다.

## 📷 기본 사용법

### 이미지에서 텍스트 추출

```bash
python ocr.py photo.jpg
# → photo.md 파일로 저장
```

### PDF 문서 처리

```bash
python ocr.py document.pdf
# → document.md 파일로 저장
```

### 실시간 스트리밍

```bash
python ocr.py document.pdf
# 화면에 텍스트가 실시간으로 표시됩니다
```

## 주요 옵션

```bash
# 조용한 모드 (화면 출력 최소화)
python ocr.py --quiet document.pdf

# 파일 저장 없이 화면 출력만
python ocr.py --no-save document.pdf

# 통계 표시
python ocr.py --stats document.pdf

# 오류 건너뛰고 계속 진행 (PDF)
python ocr.py --skip-errors book.pdf

# 중단된 작업 이어서 하기 (PDF)
python ocr.py --resume large_document.pdf
```

## 설정 파일

### YAML 설정 파일 만들기

```bash
# 기본 설정 파일 생성
python ocr.py --create-config ocr_config.yml
```

### 설정 파일 사용하기

```bash
# 설정 파일로 실행
python ocr.py -c ocr_config.yml document.pdf
```

### 설정 파일 예시

```yaml
# ocr_config.yml
ocr:
  streaming: true      # 실시간 스트리밍
  save_mode: "token"   # 저장 모드
  save_file: true      # 파일 저장
  quiet: false         # 조용한 모드

pdf:
  skip_errors: true    # 오류 페이지 건너뛰기
  max_retries: 2       # 재시도 횟수
```

## 💡 활용 예시

### 스캔한 문서를 텍스트로
```bash
python ocr.py scanned_document.pdf
```

### 스크린샷에서 텍스트 복사
```bash
python ocr.py screenshot.png --no-save
# 화면에 나온 텍스트를 복사
```

### 대용량 PDF 처리
```bash
# 오류가 나도 계속 진행
python ocr.py --skip-errors large_book.pdf

# 중간에 멈췄다면 이어서 진행
python ocr.py --resume large_book.pdf
```

## 📋 시스템 요구사항

- **macOS** 12.0 이상
- **Apple Silicon** (M1/M2/M3)
- **메모리** 8GB 이상 (16GB 권장)
- **저장공간** 10GB 이상

## 🔧 설치 상세

### 수동 설치 (문제가 있을 때)

1. **Homebrew 설치**
```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

2. **필요한 도구 설치**
```bash
brew install llama.cpp python@3.12 uv poppler
```

3. **Python 환경 설정**
```bash
uv venv .venv
source .venv/bin/activate
uv pip install -r requirements.txt
```

##문제 해결

### 서버가 안 켜질 때
```bash
# 포트 확인
lsof -i :8080
# 사용 중이면 종료
kill $(lsof -t -i:8080)
```

### OCR이 너무 느릴 때
```bash
# GPU 가속 확인 (로그에서 "Metal" 또는 "MPS" 찾기)
./start_server.sh
```

### 모델 다운로드 실패
```bash
# 수동 다운로드
llama-cli -hf ggml-org/LightOnOCR-1B-1025-GGUF --help
```

## API 사용

### Python으로 연동
```python
import base64
import httpx

def ocr_image(image_path):
    with open(image_path, "rb") as f:
        image_base64 = base64.b64encode(f.read()).decode()

    response = httpx.post(
        "http://localhost:8080/v1/chat/completions",
        json={
            "model": "LightOnOCR-1B-1025",
            "messages": [{
                "role": "user",
                "content": [
                    {"type": "text", "text": "Extract all text from this image."},
                    {"type": "image_url", "image_url": {
                        "url": f"data:image/jpeg;base64,{image_base64}"
                    }}
                ]
            }],
            "temperature": 0.1,
            "max_tokens": 4096
        }
    )
    return response.json()["choices"][0]["message"]["content"]
```

### curl로 직접 호출
```bash
# 헬스 체크
curl http://localhost:8080/health

# 모델 정보
curl http://localhost:8080/v1/models
```

## 더 알아보기

- [고급 설정 가이드](docs/ADVANCED.md)
- [API 상세 문서](docs/API.md)
- [설정 파일 전체 옵션](docs/CONFIGURATION.md)
- [문제 해결 가이드](docs/TROUBLESHOOTING.md)

## 관련 링크

- [llama.cpp](https://github.com/ggml-org/llama.cpp)
- [LightOnOCR 모델](https://huggingface.co/ggml-org/LightOnOCR-1B-1025-GGUF)

## 라이선스

MIT 라이선스