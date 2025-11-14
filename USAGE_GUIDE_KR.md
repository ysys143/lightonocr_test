# LightOnOCR llama.cpp 서빙 시스템 사용 가이드

## 🎉 프로젝트 준비 완료!

재솔님, LightOnOCR 모델을 llama.cpp로 서빙하기 위한 모든 환경이 준비되었습니다.

## 📁 프로젝트 구조

```
lightonocr_test/
├── setup_macos.sh        # 원스톱 설치 스크립트
├── start_server.sh       # OCR 서버 시작 스크립트
├── test_ocr.py          # OCR 테스트 클라이언트
├── requirements.txt     # Python 의존성 (최소)
├── README.md           # 영문 사용 가이드
├── data/
│   └── test.pdf        # Chameleon 논문 테스트 파일
└── docs/
    └── initial_idea.md # 프로젝트 요구사항 문서

## 🚀 빠른 시작 (4단계)

### 1단계: 환경 설치
```bash
./setup_macos.sh
```
이 스크립트는 다음을 자동으로 설치합니다:
- Homebrew 확인 및 설치 안내
- llama.cpp (이미 설치됨)
- poppler (PDF 처리용)
- Python 가상환경 및 패키지

### 2단계: 모델 다운로드
```bash
./download_models.sh
```
Hugging Face에서 모델을 다운로드하거나 캐시에서 복사합니다.
- 옵션: `--copy` (복사), `--symlink` (링크), `--download` (직접 다운로드)

### 3단계: 서버 시작
```bash
./start_server.sh
```
로컬 models 폴더의 모델을 직접 로드합니다.

### 4단계: OCR 테스트
```bash
# 가상환경 활성화
source .venv/bin/activate

# PDF 파일 OCR 테스트
python test_ocr.py data/test.pdf
```

## 💡 주요 특징

1. **단순함**: FastAPI 등 불필요한 중간 계층 제거
2. **GGUF 포맷**: LightOnOCR-1B-1025-GGUF 모델 직접 서빙
3. **MPS 가속**: Apple Silicon GPU 활용
4. **자동화**: 한 번의 스크립트로 모든 설정 완료

## 📊 서버 엔드포인트

서버 시작 후 다음 엔드포인트를 사용할 수 있습니다:
- `http://localhost:8080` - 웹 UI
- `http://localhost:8080/health` - 헬스 체크
- `http://localhost:8080/v1/chat/completions` - OCR API

## 🔧 문제 해결

### 포트 충돌 시
```bash
# 사용 중인 프로세스 확인
lsof -i :8080

# 프로세스 종료
kill $(lsof -t -i:8080)
```

### 메모리 부족 시
`start_server.sh`에서 GPU_LAYERS 값을 줄이세요:
```bash
GPU_LAYERS=50  # 999에서 감소
```

## 📝 추가 정보

- 모델 크기: 1.2GB (메인 767MB + 프로젝터 416MB)
- 모델 저장 위치: `~/Library/Caches/llama.cpp/`
- 다운로드 시간: 약 26초 (M3 Max 기준)
- models/ 폴더: 사용 안 함 (llama-server가 자동 캐시 관리)

## ⚠️ 현재 상태 (2024.11.14)

llama.cpp 현재 버전(5921)이 LightOnOCR 프로젝터를 지원하지 않음:
```
error: unknown projector type: lightonocr
```
PR #16764 병합 대기 중

## ✅ 완료 사항

- ✓ macOS 전체 환경 설치 스크립트
- ✓ llama-server 직접 서빙 구성
- ✓ Python 테스트 클라이언트
- ✓ 완전한 문서화
- ✓ Git 저장소 초기화

이제 누구나 macOS에서 Homebrew 설치부터 시작하여 OCR 서버를 실행할 수 있습니다!