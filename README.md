# LightOnOCR - llama.cpp 기반 OCR 서버

Apple Silicon MPS 가속을 활용한 고성능 로컬 OCR 서비스

## 🚀 빠른 시작 (10분 내 설치)

macOS에서 단 3개의 명령으로 OCR 서버를 시작할 수 있습니다:

```bash
# 1. 프로젝트 클론
git clone https://github.com/yourusername/lightonocr_test.git
cd lightonocr_test

# 2. 자동 설치 (Homebrew 설치부터 모든 환경 구성)
./setup_macos.sh

# 3. OCR 서버 시작
./start_server.sh
```

서버가 시작되면 http://localhost:8080 에서 바로 사용할 수 있습니다!

## 📋 시스템 요구사항

- **macOS** 12.0 이상
- **Apple Silicon** (M1/M2/M3/M4) 또는 Intel Mac
- **메모리** 8GB 이상 (16GB 권장)
- **저장공간** 10GB 이상

## 🛠️ 상세 설치 가이드

### 1단계: Homebrew 설치 (이미 있다면 건너뛰기)

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

설치 후 PATH 설정:
```bash
# Apple Silicon Mac
echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> ~/.zshrc
source ~/.zshrc

# Intel Mac
echo 'eval "$(/usr/local/bin/brew shellenv)"' >> ~/.zshrc
source ~/.zshrc
```

### 2단계: 프로젝트 설정

```bash
# 프로젝트 클론
git clone https://github.com/yourusername/lightonocr_test.git
cd lightonocr_test

# 자동 설치 스크립트 실행
chmod +x setup_macos.sh
./setup_macos.sh
```

`setup_macos.sh`는 다음을 자동으로 설치합니다:
- llama.cpp (MPS 가속 지원)
- Python 3.12 및 uv 패키지 관리자
- poppler (PDF 처리용)
- 필요한 Python 패키지들

### 3단계: 서버 시작

```bash
chmod +x start_server.sh
./start_server.sh
```

첫 실행 시 모델 다운로드로 5-10분이 소요될 수 있습니다 (약 2GB).

## 🧪 테스트

### Python 클라이언트로 테스트

```bash
# 가상환경 활성화
source .venv/bin/activate

# PDF 파일 OCR
python test_ocr.py data/test.pdf

# 이미지 파일 OCR
python test_ocr.py image.png
```

### curl로 직접 API 호출

```bash
# 헬스 체크
curl http://localhost:8080/health

# 모델 정보
curl http://localhost:8080/v1/models

# 이미지 OCR (base64 인코딩 필요)
IMAGE_BASE64=$(base64 -i image.jpg)
curl -X POST http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d "{
    \"model\": \"LightOnOCR-1B-1025\",
    \"messages\": [{
      \"role\": \"user\",
      \"content\": [
        {\"type\": \"text\", \"text\": \"Extract all text from this image.\"},
        {\"type\": \"image_url\", \"image_url\": {\"url\": \"data:image/jpeg;base64,$IMAGE_BASE64\"}}
      ]
    }],
    \"temperature\": 0.1,
    \"max_tokens\": 4096
  }"
```

## 📖 API 사용법

### Python 예제

```python
import base64
import httpx

def ocr_image(image_path):
    # 이미지를 base64로 인코딩
    with open(image_path, "rb") as f:
        image_base64 = base64.b64encode(f.read()).decode()

    # API 요청
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

    result = response.json()
    return result["choices"][0]["message"]["content"]

# 사용
text = ocr_image("document.jpg")
print(text)
```

### JavaScript/TypeScript 예제

```javascript
async function ocrImage(imagePath) {
    // 이미지를 base64로 인코딩 (Node.js)
    const fs = require('fs');
    const imageBase64 = fs.readFileSync(imagePath, {encoding: 'base64'});

    const response = await fetch('http://localhost:8080/v1/chat/completions', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
            model: 'LightOnOCR-1B-1025',
            messages: [{
                role: 'user',
                content: [
                    {type: 'text', text: 'Extract all text from this image.'},
                    {type: 'image_url', image_url: {
                        url: `data:image/jpeg;base64,${imageBase64}`
                    }}
                ]
            }],
            temperature: 0.1,
            max_tokens: 4096
        })
    });

    const result = await response.json();
    return result.choices[0].message.content;
}
```

## 🎯 지원 형식

- **이미지**: PNG, JPG, JPEG, BMP, GIF, TIFF
- **문서**: PDF (자동으로 이미지로 변환)

## ⚙️ 설정 옵션

### 서버 포트 변경

`start_server.sh`를 편집하여 PORT 변수 수정:
```bash
PORT=8080  # 원하는 포트로 변경
```

### GPU 메모리 최적화

메모리가 부족한 경우 `start_server.sh`에서 GPU 레이어 수 조정:
```bash
GPU_LAYERS=50  # 999 대신 더 작은 값 사용
```

### 컨텍스트 크기 조정

더 긴 텍스트 처리가 필요한 경우:
```bash
CONTEXT_SIZE=16384  # 기본 8192에서 증가
```

## 🐛 문제 해결

### 서버가 시작되지 않음
```bash
# 포트가 사용 중인지 확인
lsof -i :8080
# 사용 중이면 프로세스 종료
kill $(lsof -t -i:8080)
```

### 모델 다운로드 실패
```bash
# 수동으로 모델 다운로드 시도
llama-cli -hf ggml-org/LightOnOCR-1B-1025-GGUF --help
```

### Python 패키지 설치 실패
```bash
# 가상환경 재생성
rm -rf .venv
uv venv .venv
source .venv/bin/activate
uv pip install httpx pillow pdf2image
```

### MPS 가속이 작동하지 않음
```bash
# CPU 모드로 실행 (느림)
# start_server.sh에서 GPU_LAYERS=0으로 설정
```

## 📊 성능

Apple M3 Max (36GB) 기준:
- 단일 이미지 OCR: 1-3초
- A4 PDF 페이지: 2-5초
- 메모리 사용량: 약 4-6GB

## 🔗 관련 링크

- [llama.cpp GitHub](https://github.com/ggml-org/llama.cpp)
- [LightOnOCR-1B 모델](https://huggingface.co/ggml-org/LightOnOCR-1B-1025-GGUF)
- [원본 모델 정보](https://huggingface.co/lightonai/LightOnOCR-1B-1025)

## 📜 라이선스

이 프로젝트는 MIT 라이선스를 따릅니다. LightOnOCR 모델은 별도의 라이선스를 가질 수 있으니 확인하세요.

## 🤝 기여

버그 리포트와 기능 제안은 GitHub Issues를 통해 제출해주세요.

---

Made with ❤️ for the macOS community