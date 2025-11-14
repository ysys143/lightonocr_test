llama.cpp 프레임워크를 활용하여 고성능 OCR(Optical Character Recognition) 서빙 시스템을 구축한다. 이 시스템은 llama.cpp의 PR #16764에서 제안된 OCR 기능을 기반으로 하며, Apple Silicon의 MPS(Metal Performance Shaders) 가속을 활용하여 로컬 환경에서도 빠른 추론 속도를 보장한다. 주요 목표는 PDF 및 이미지 파일에서 텍스트를 추출하는 REST API 서버를 구현하고, llama.cpp의 경량화된 모델 서빙 기능을 통해 리소스 효율적인 OCR 파이프라인을 구성하는 것이다. 시스템은 FastAPI 기반 웹 서버로 제공되며, 다양한 이미지 포맷과 PDF 문서를 지원하여 실무에서 즉시 활용 가능한 OCR 솔루션을 제공한다.

## 기술 구현 세부사항

본 시스템은 LightOnOCR-1B-1025 모델의 GGUF 양자화 버전을 사용하여 구현된다. 이 모델은 Qwen3 언어 모델과 Mistral3 비전 인코더를 결합한 아키텍처로, 1B 규모의 경량 모델임에도 높은 OCR 성능을 제공한다. llama-server를 통해 직접 모델을 서빙하며, Hugging Face 리포지토리(ggml-org/LightOnOCR-1B-1025-GGUF)에서 자동으로 모델을 다운로드하여 실행한다. 서버는 8192 토큰의 컨텍스트 크기로 구성되며, MPS 가속을 위해 최대 GPU 레이어를 활용한다. FastAPI 래퍼를 통해 이미지 업로드, OCR 처리, 결과 반환의 완전한 파이프라인을 제공하며, PDF 파일의 경우 pdf2image를 통해 이미지로 변환 후 처리한다.

