#!/usr/bin/env python3
"""
LightOnOCR 테스트 클라이언트
llama-server의 OpenAI 호환 API를 사용하여 이미지와 PDF에서 텍스트를 추출합니다.
"""

import base64
import json
import sys
import time
from pathlib import Path
from typing import List, Optional

import httpx
from PIL import Image
from pdf2image import convert_from_path

# 서버 설정
SERVER_URL = "http://localhost:8080"
API_ENDPOINT = f"{SERVER_URL}/v1/chat/completions"
HEALTH_ENDPOINT = f"{SERVER_URL}/health"
MODEL_NAME = "LightOnOCR-1B-1025"


def check_server_health() -> bool:
    """서버 상태를 확인합니다."""
    try:
        response = httpx.get(HEALTH_ENDPOINT, timeout=5)
        if response.status_code == 200:
            print("✅ 서버가 정상적으로 실행 중입니다")
            return True
    except httpx.ConnectError:
        print("❌ 서버에 연결할 수 없습니다")
        print("   ./start_server.sh를 실행하여 서버를 시작해주세요")
    except Exception as e:
        print(f"❌ 서버 확인 중 오류 발생: {e}")
    return False


def image_to_base64(image_path: Path) -> str:
    """이미지 파일을 base64 문자열로 변환합니다."""
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")


def pdf_to_images(pdf_path: Path) -> List[Image.Image]:
    """PDF 파일을 이미지 리스트로 변환합니다."""
    try:
        images = convert_from_path(pdf_path, dpi=200)
        print(f"📄 PDF를 {len(images)}개의 이미지로 변환했습니다")
        return images
    except Exception as e:
        print(f"❌ PDF 변환 실패: {e}")
        return []


def perform_ocr(image_base64: str, prompt: str = "Extract all text from this image.") -> Optional[str]:
    """이미지에서 텍스트를 추출합니다."""

    # 요청 데이터 구성
    request_data = {
        "model": MODEL_NAME,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{image_base64}"
                        }
                    }
                ]
            }
        ],
        "temperature": 0.1,
        "max_tokens": 4096,
        "stream": False
    }

    try:
        # API 호출
        response = httpx.post(
            API_ENDPOINT,
            json=request_data,
            timeout=60  # OCR은 시간이 걸릴 수 있음
        )

        if response.status_code == 200:
            result = response.json()
            if "choices" in result and len(result["choices"]) > 0:
                return result["choices"][0]["message"]["content"]
            else:
                print("⚠️ 예상치 못한 응답 형식")
                return None
        else:
            print(f"❌ API 오류: {response.status_code}")
            print(f"   응답: {response.text}")
            return None

    except httpx.TimeoutException:
        print("⏱️ 요청 시간 초과")
        return None
    except Exception as e:
        print(f"❌ OCR 처리 중 오류: {e}")
        return None


def process_image_file(image_path: Path):
    """이미지 파일을 처리합니다."""
    print(f"\n🖼️ 이미지 처리: {image_path.name}")
    print("-" * 40)

    if not image_path.exists():
        print(f"❌ 파일을 찾을 수 없습니다: {image_path}")
        return

    # 이미지를 base64로 변환
    start_time = time.time()
    image_base64 = image_to_base64(image_path)

    # OCR 수행
    print("🔍 OCR 처리 중...")
    extracted_text = perform_ocr(image_base64)

    elapsed_time = time.time() - start_time

    if extracted_text:
        print(f"✅ 텍스트 추출 완료 ({elapsed_time:.2f}초)")
        print("\n📝 추출된 텍스트:")
        print("-" * 40)
        print(extracted_text)
        print("-" * 40)

        # 결과를 마크다운 파일로 저장
        output_path = image_path.with_suffix(".md")
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(f"# OCR 결과: {image_path.name}\n\n")
            f.write(f"**처리 시간**: {elapsed_time:.2f}초\n\n")
            f.write("---\n\n")
            f.write(extracted_text)
        print(f"\n💾 텍스트가 저장되었습니다: {output_path}")
    else:
        print("❌ 텍스트 추출 실패")


def process_pdf_file(pdf_path: Path):
    """PDF 파일을 처리합니다."""
    print(f"\n📄 PDF 처리: {pdf_path.name}")
    print("-" * 40)

    if not pdf_path.exists():
        print(f"❌ 파일을 찾을 수 없습니다: {pdf_path}")
        return

    # PDF를 이미지로 변환
    images = pdf_to_images(pdf_path)
    if not images:
        return

    # 출력 파일 경로 설정
    output_path = pdf_path.with_suffix(".md")
    all_text = []
    total_start_time = time.time()

    # 파일 초기화 - 헤더 작성
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(f"# OCR 결과: {pdf_path.name}\n\n")
        f.write(f"**총 페이지 수**: {len(images)}페이지\n\n")
        f.write("---\n\n")

    print(f"📝 결과 파일 생성: {output_path}")

    # 각 페이지 처리
    for i, image in enumerate(images, 1):
        print(f"\n📖 페이지 {i}/{len(images)} 처리 중...")

        try:
            # PIL Image를 base64로 변환
            import io
            buffer = io.BytesIO()
            image.save(buffer, format="JPEG", quality=95)
            image_base64 = base64.b64encode(buffer.getvalue()).decode()

            # OCR 수행
            extracted_text = perform_ocr(
                image_base64,
                f"Extract all text from page {i} of this document."
            )

            if extracted_text:
                all_text.append(f"[페이지 {i}]\n{extracted_text}")

                # 각 페이지 처리 즉시 파일에 추가
                with open(output_path, "a", encoding="utf-8") as f:
                    f.write(f"## 페이지 {i}\n\n")
                    f.write(extracted_text + "\n\n")
                    if i < len(images):
                        f.write("---\n\n")

                print(f"✅ 페이지 {i} 완료 및 저장")
            else:
                print(f"⚠️ 페이지 {i} 텍스트 추출 실패")
                # 실패한 페이지도 기록
                with open(output_path, "a", encoding="utf-8") as f:
                    f.write(f"## 페이지 {i}\n\n")
                    f.write("*[텍스트 추출 실패]*\n\n")
                    if i < len(images):
                        f.write("---\n\n")

        except Exception as e:
            print(f"❌ 페이지 {i} 처리 중 오류: {e}")
            # 오류 발생 시에도 기록
            with open(output_path, "a", encoding="utf-8") as f:
                f.write(f"## 페이지 {i}\n\n")
                f.write(f"*[처리 오류: {str(e)}]*\n\n")
                if i < len(images):
                    f.write("---\n\n")

    total_elapsed = time.time() - total_start_time

    # 마지막에 처리 시간 추가
    with open(output_path, "a", encoding="utf-8") as f:
        f.write(f"\n---\n\n**전체 처리 시간**: {total_elapsed:.2f}초\n")

    if all_text:
        print(f"\n✅ 전체 PDF 처리 완료 ({total_elapsed:.2f}초)")
        print(f"💾 텍스트가 저장되었습니다: {output_path}")
        print(f"   총 {len(all_text)}개 페이지 성공적으로 처리")
    else:
        print("⚠️ PDF 처리가 완료되었으나 텍스트를 추출할 수 없었습니다")
        print(f"   결과 파일: {output_path}")


def main():
    """메인 함수"""
    print("=" * 50)
    print("   LightOnOCR 테스트 클라이언트")
    print("=" * 50)

    # 서버 상태 확인
    if not check_server_health():
        sys.exit(1)

    # 명령줄 인자 처리
    if len(sys.argv) < 2:
        print("\n사용법:")
        print("  python test_ocr.py <파일경로>")
        print("\n예제:")
        print("  python test_ocr.py data/test.pdf")
        print("  python test_ocr.py image.png")
        print("\n기본 테스트 파일로 진행합니다...")

        # 기본 테스트 파일 찾기
        test_files = [
            Path("data/test.pdf"),
            Path("test_pdf.pdf"),
            Path("data/test_images/sample.png"),
            Path("data/test_images/sample.jpg")
        ]

        test_file = None
        for f in test_files:
            if f.exists():
                test_file = f
                break

        if not test_file:
            print("❌ 테스트 파일을 찾을 수 없습니다")
            sys.exit(1)
    else:
        test_file = Path(sys.argv[1])

    # 파일 형식에 따라 처리
    if test_file.suffix.lower() == ".pdf":
        process_pdf_file(test_file)
    elif test_file.suffix.lower() in [".png", ".jpg", ".jpeg", ".bmp", ".gif", ".tiff"]:
        process_image_file(test_file)
    else:
        print(f"❌ 지원하지 않는 파일 형식: {test_file.suffix}")
        print("   지원 형식: PDF, PNG, JPG, JPEG, BMP, GIF, TIFF")
        sys.exit(1)

    print("\n✅ 테스트 완료!")


if __name__ == "__main__":
    main()