#!/usr/bin/env python3
"""
LightOnOCR 스트리밍 테스트 클라이언트
실시간으로 OCR 결과를 스트리밍으로 받아 처리합니다.
"""

import base64
import json
import sys
import time
from pathlib import Path
from typing import Iterator, Optional

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


def pdf_to_images(pdf_path: Path) -> list[Image.Image]:
    """PDF 파일을 이미지 리스트로 변환합니다."""
    try:
        images = convert_from_path(pdf_path, dpi=200)
        print(f"📄 PDF를 {len(images)}개의 이미지로 변환했습니다")
        return images
    except Exception as e:
        print(f"❌ PDF 변환 실패: {e}")
        return []


def perform_ocr_stream(
    image_base64: str,
    prompt: str = "Extract all text from this image.",
    output_file: Optional[Path] = None
) -> Iterator[str]:
    """이미지에서 텍스트를 추출하며 실시간으로 스트리밍합니다."""

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
        "stream": True  # 스트리밍 활성화
    }

    file_handle = None
    if output_file:
        # 버퍼링 없이 즉시 쓰기 (buffering=1은 라인 버퍼링)
        file_handle = open(output_file, "a", encoding="utf-8", buffering=1)

    try:
        # 스트리밍 요청
        buffer = ""  # 문장/문단 감지용 버퍼
        with httpx.Client(timeout=120) as client:
            with client.stream(
                "POST",
                API_ENDPOINT,
                json=request_data,
            ) as response:
                if response.status_code != 200:
                    print(f"❌ API 오류: {response.status_code}")
                    return

                # 스트리밍 응답 처리
                for line in response.iter_lines():
                    if line.startswith("data: "):
                        data = line[6:]  # "data: " 제거

                        if data == "[DONE]":
                            # 마지막 남은 버퍼 처리
                            if buffer and file_handle:
                                file_handle.write(buffer)
                                file_handle.flush()
                            break

                        try:
                            json_data = json.loads(data)
                            if "choices" in json_data and len(json_data["choices"]) > 0:
                                delta = json_data["choices"][0].get("delta", {})
                                content = delta.get("content", "")
                                if content:
                                    # 실시간으로 출력
                                    print(content, end="", flush=True)

                                    # 버퍼에 추가
                                    buffer += content

                                    # 파일에 즉시 저장 (매 청크마다)
                                    # 옵션 1: 매 토큰마다 저장 (가장 빠름)
                                    if file_handle:
                                        file_handle.write(content)
                                        file_handle.flush()  # 강제로 디스크에 쓰기
                                        # OS 레벨에서도 즉시 쓰기 보장
                                        import os
                                        os.fsync(file_handle.fileno())

                                    # 옵션 2: 문장 단위로 저장 (주석 처리됨)
                                    # if any(p in buffer for p in ['. ', '.\n', '! ', '? ', '。']):
                                    #     if file_handle:
                                    #         file_handle.write(buffer)
                                    #         file_handle.flush()
                                    #     buffer = ""

                                    # 옵션 3: 줄바꿈 단위로 저장 (주석 처리됨)
                                    # if '\n' in buffer:
                                    #     if file_handle:
                                    #         file_handle.write(buffer)
                                    #         file_handle.flush()
                                    #     buffer = ""

                                    yield content
                        except json.JSONDecodeError:
                            continue

    except httpx.TimeoutException:
        print("\n⏱️ 요청 시간 초과")
    except Exception as e:
        print(f"\n❌ OCR 처리 중 오류: {e}")
    finally:
        if file_handle:
            file_handle.flush()
            file_handle.close()


def process_image_file_stream(image_path: Path):
    """이미지 파일을 스트리밍으로 처리합니다."""
    print(f"\n🖼️ 이미지 처리 (스트리밍): {image_path.name}")
    print("-" * 40)

    if not image_path.exists():
        print(f"❌ 파일을 찾을 수 없습니다: {image_path}")
        return

    # 출력 파일 경로
    output_path = image_path.with_suffix(".md")

    # 파일 초기화
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(f"# OCR 결과: {image_path.name}\n\n")
        f.write("**처리 방식**: 실시간 스트리밍\n\n")
        f.write("---\n\n")

    print(f"📝 결과 파일: {output_path}")
    print(f"🔍 OCR 처리 중 (실시간 스트리밍)...\n")
    print("=" * 50)

    # 이미지를 base64로 변환
    start_time = time.time()
    image_base64 = image_to_base64(image_path)

    # OCR 수행 (스트리밍)
    total_text = ""
    for chunk in perform_ocr_stream(image_base64, output_file=output_path):
        total_text += chunk

    elapsed_time = time.time() - start_time

    print("\n" + "=" * 50)

    # 마지막에 처리 시간 추가
    with open(output_path, "a", encoding="utf-8") as f:
        f.write(f"\n\n---\n\n**처리 시간**: {elapsed_time:.2f}초\n")

    if total_text:
        print(f"\n✅ 텍스트 추출 완료 ({elapsed_time:.2f}초)")
        print(f"💾 텍스트가 저장되었습니다: {output_path}")
    else:
        print("❌ 텍스트 추출 실패")


def process_pdf_file_stream(pdf_path: Path):
    """PDF 파일을 스트리밍으로 처리합니다."""
    print(f"\n📄 PDF 처리 (스트리밍): {pdf_path.name}")
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

    # 파일 초기화 - 헤더 작성
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(f"# OCR 결과: {pdf_path.name}\n\n")
        f.write(f"**총 페이지 수**: {len(images)}페이지\n")
        f.write("**처리 방식**: 실시간 스트리밍\n\n")
        f.write("---\n\n")

    print(f"📝 결과 파일: {output_path}")
    total_start_time = time.time()

    # 각 페이지 처리
    for i, image in enumerate(images, 1):
        print(f"\n📖 페이지 {i}/{len(images)} 처리 중 (스트리밍)...")
        print("-" * 40)

        try:
            # PIL Image를 base64로 변환
            import io
            buffer = io.BytesIO()
            image.save(buffer, format="JPEG", quality=95)
            image_base64 = base64.b64encode(buffer.getvalue()).decode()

            # 페이지 헤더 추가
            with open(output_path, "a", encoding="utf-8") as f:
                f.write(f"## 페이지 {i}\n\n")

            # OCR 수행 (스트리밍)
            page_text = ""
            for chunk in perform_ocr_stream(
                image_base64,
                f"Extract all text from page {i} of this document.",
                output_file=output_path
            ):
                page_text += chunk

            # 페이지 구분자 추가
            with open(output_path, "a", encoding="utf-8") as f:
                f.write("\n\n")
                if i < len(images):
                    f.write("---\n\n")

            if page_text:
                print(f"\n✅ 페이지 {i} 완료")
            else:
                print(f"\n⚠️ 페이지 {i} 텍스트 추출 실패")
                with open(output_path, "a", encoding="utf-8") as f:
                    f.write("*[텍스트 추출 실패]*\n\n")

        except Exception as e:
            print(f"\n❌ 페이지 {i} 처리 중 오류: {e}")
            with open(output_path, "a", encoding="utf-8") as f:
                f.write(f"*[처리 오류: {str(e)}]*\n\n")
                if i < len(images):
                    f.write("---\n\n")

    total_elapsed = time.time() - total_start_time

    # 마지막에 처리 시간 추가
    with open(output_path, "a", encoding="utf-8") as f:
        f.write(f"\n---\n\n**전체 처리 시간**: {total_elapsed:.2f}초\n")

    print(f"\n✅ 전체 PDF 처리 완료 ({total_elapsed:.2f}초)")
    print(f"💾 텍스트가 저장되었습니다: {output_path}")


def main():
    """메인 함수"""
    print("=" * 50)
    print("   LightOnOCR 스트리밍 테스트 클라이언트")
    print("=" * 50)

    # 서버 상태 확인
    if not check_server_health():
        sys.exit(1)

    # 명령줄 인자 처리
    if len(sys.argv) < 2:
        print("\n사용법:")
        print("  python test_ocr_stream.py <파일경로>")
        print("\n예제:")
        print("  python test_ocr_stream.py data/test.pdf")
        print("  python test_ocr_stream.py image.png")
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
        process_pdf_file_stream(test_file)
    elif test_file.suffix.lower() in [".png", ".jpg", ".jpeg", ".bmp", ".gif", ".tiff"]:
        process_image_file_stream(test_file)
    else:
        print(f"❌ 지원하지 않는 파일 형식: {test_file.suffix}")
        print("   지원 형식: PDF, PNG, JPG, JPEG, BMP, GIF, TIFF")
        sys.exit(1)

    print("\n✅ 스트리밍 테스트 완료!")


if __name__ == "__main__":
    main()