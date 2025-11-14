#!/usr/bin/env python3
"""
LightOnOCR 고급 스트리밍 클라이언트
다양한 파일 저장 모드를 지원하는 실시간 OCR 스트리밍
"""

import base64
import json
import sys
import time
from pathlib import Path
from typing import Iterator, Optional, Literal
from enum import Enum

import httpx
from PIL import Image
from pdf2image import convert_from_path

# 서버 설정
SERVER_URL = "http://localhost:8080"
API_ENDPOINT = f"{SERVER_URL}/v1/chat/completions"
HEALTH_ENDPOINT = f"{SERVER_URL}/health"
MODEL_NAME = "LightOnOCR-1B-1025"


class SaveMode(Enum):
    """파일 저장 모드"""
    TOKEN = "token"          # 매 토큰마다 저장 (가장 빠름)
    WORD = "word"           # 단어 단위로 저장
    SENTENCE = "sentence"    # 문장 단위로 저장
    PARAGRAPH = "paragraph"  # 문단 단위로 저장
    LINE = "line"           # 줄 단위로 저장


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


def should_save_buffer(buffer: str, mode: SaveMode) -> bool:
    """버퍼를 저장해야 하는지 결정합니다."""
    if mode == SaveMode.TOKEN:
        return True  # 항상 즉시 저장
    elif mode == SaveMode.WORD:
        return ' ' in buffer or '\n' in buffer or '\t' in buffer
    elif mode == SaveMode.SENTENCE:
        return any(p in buffer for p in ['. ', '.\n', '! ', '!\n', '? ', '?\n', '。', '；'])
    elif mode == SaveMode.PARAGRAPH:
        return '\n\n' in buffer or buffer.count('\n') >= 2
    elif mode == SaveMode.LINE:
        return '\n' in buffer
    return False


def perform_ocr_stream_advanced(
    image_base64: str,
    prompt: str = "Extract all text from this image.",
    output_file: Optional[Path] = None,
    save_mode: SaveMode = SaveMode.TOKEN,
    show_stats: bool = True
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
        "stream": True
    }

    file_handle = None
    if output_file:
        # 버퍼링 설정: TOKEN 모드는 버퍼링 없이, 나머지는 라인 버퍼링
        buffering = 0 if save_mode == SaveMode.TOKEN else 1
        file_handle = open(output_file, "a", encoding="utf-8", buffering=buffering)

    # 통계 변수
    stats = {
        "tokens": 0,
        "saves": 0,
        "start_time": time.time(),
        "first_token_time": None
    }

    try:
        buffer = ""
        with httpx.Client(timeout=120) as client:
            with client.stream("POST", API_ENDPOINT, json=request_data) as response:
                if response.status_code != 200:
                    print(f"❌ API 오류: {response.status_code}")
                    return

                for line in response.iter_lines():
                    if line.startswith("data: "):
                        data = line[6:]

                        if data == "[DONE]":
                            # 마지막 버퍼 처리
                            if buffer and file_handle:
                                file_handle.write(buffer)
                                file_handle.flush()
                                stats["saves"] += 1
                            break

                        try:
                            json_data = json.loads(data)
                            if "choices" in json_data and len(json_data["choices"]) > 0:
                                delta = json_data["choices"][0].get("delta", {})
                                content = delta.get("content", "")

                                if content:
                                    # 첫 토큰 시간 기록
                                    if stats["first_token_time"] is None:
                                        stats["first_token_time"] = time.time()

                                    stats["tokens"] += 1

                                    # 화면 출력
                                    print(content, end="", flush=True)

                                    # 저장 모드에 따른 처리
                                    if save_mode == SaveMode.TOKEN:
                                        # 즉시 저장
                                        if file_handle:
                                            file_handle.write(content)
                                            file_handle.flush()
                                            # 강제 디스크 동기화
                                            import os
                                            os.fsync(file_handle.fileno())
                                            stats["saves"] += 1
                                    else:
                                        # 버퍼에 추가하고 조건 확인
                                        buffer += content
                                        if should_save_buffer(buffer, save_mode):
                                            if file_handle:
                                                file_handle.write(buffer)
                                                file_handle.flush()
                                                stats["saves"] += 1
                                            buffer = ""

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

        # 통계 출력
        if show_stats and stats["first_token_time"]:
            elapsed = time.time() - stats["start_time"]
            time_to_first = stats["first_token_time"] - stats["start_time"]

            print(f"\n\n📊 스트리밍 통계:")
            print(f"   저장 모드: {save_mode.value}")
            print(f"   총 토큰 수: {stats['tokens']}")
            print(f"   파일 저장 횟수: {stats['saves']}")
            print(f"   첫 토큰까지: {time_to_first:.2f}초")
            print(f"   전체 시간: {elapsed:.2f}초")
            print(f"   토큰/초: {stats['tokens']/elapsed:.1f}")


def process_image_file_advanced(
    image_path: Path,
    save_mode: SaveMode = SaveMode.TOKEN
):
    """이미지 파일을 고급 스트리밍으로 처리합니다."""
    print(f"\n🖼️ 이미지 처리 (스트리밍 - {save_mode.value} 모드): {image_path.name}")
    print("-" * 40)

    if not image_path.exists():
        print(f"❌ 파일을 찾을 수 없습니다: {image_path}")
        return

    # 출력 파일 경로
    output_path = image_path.with_suffix(f".{save_mode.value}.md")

    # 파일 초기화
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(f"# OCR 결과: {image_path.name}\n\n")
        f.write(f"**처리 방식**: 실시간 스트리밍 ({save_mode.value} 모드)\n\n")
        f.write("---\n\n")

    print(f"📝 결과 파일: {output_path}")
    print(f"💾 저장 모드: {save_mode.value}")
    print(f"🔍 OCR 처리 중...\n")
    print("=" * 50)

    # 이미지를 base64로 변환
    start_time = time.time()
    image_base64 = image_to_base64(image_path)

    # OCR 수행
    total_text = ""
    for chunk in perform_ocr_stream_advanced(
        image_base64,
        output_file=output_path,
        save_mode=save_mode
    ):
        total_text += chunk

    elapsed_time = time.time() - start_time

    print("\n" + "=" * 50)

    # 처리 시간 추가
    with open(output_path, "a", encoding="utf-8") as f:
        f.write(f"\n\n---\n\n**전체 처리 시간**: {elapsed_time:.2f}초\n")

    if total_text:
        print(f"\n✅ 텍스트 추출 완료")
        print(f"💾 저장 완료: {output_path}")


def main():
    """메인 함수"""
    print("=" * 50)
    print("   LightOnOCR 고급 스트리밍 클라이언트")
    print("=" * 50)

    # 서버 상태 확인
    if not check_server_health():
        sys.exit(1)

    # 명령줄 인자 처리
    save_mode = SaveMode.TOKEN  # 기본값
    file_path = None

    # 인자 파싱
    args = sys.argv[1:]
    for i, arg in enumerate(args):
        if arg in ["--mode", "-m"] and i + 1 < len(args):
            mode_str = args[i + 1].lower()
            try:
                save_mode = SaveMode(mode_str)
            except ValueError:
                print(f"⚠️ 알 수 없는 모드: {mode_str}")
                print(f"   사용 가능한 모드: {', '.join([m.value for m in SaveMode])}")
                save_mode = SaveMode.TOKEN
        elif not arg.startswith("-") and file_path is None:
            file_path = Path(arg)

    if file_path is None:
        print("\n사용법:")
        print("  python test_ocr_stream_advanced.py [옵션] <파일경로>")
        print("\n옵션:")
        print("  -m, --mode <모드>  저장 모드 선택")
        print(f"                     가능한 값: {', '.join([m.value for m in SaveMode])}")
        print(f"                     기본값: {SaveMode.TOKEN.value}")
        print("\n예제:")
        print("  python test_ocr_stream_advanced.py image.png")
        print("  python test_ocr_stream_advanced.py --mode sentence document.jpg")
        print("  python test_ocr_stream_advanced.py -m paragraph data/test.pdf")

        # 기본 테스트 파일
        test_files = [
            Path("data/test.pdf"),
            Path("data/test_images/sample.png")
        ]

        for f in test_files:
            if f.exists():
                file_path = f
                print(f"\n기본 테스트 파일 사용: {file_path}")
                break

        if file_path is None:
            print("\n❌ 테스트 파일을 찾을 수 없습니다")
            sys.exit(1)

    # 파일 처리
    print(f"\n선택된 저장 모드: {save_mode.value}")

    if file_path.suffix.lower() in [".png", ".jpg", ".jpeg", ".bmp", ".gif", ".tiff"]:
        process_image_file_advanced(file_path, save_mode)
    else:
        print(f"❌ 이 스크립트는 이미지 파일만 지원합니다")
        print(f"   PDF는 test_ocr_stream.py를 사용하세요")
        sys.exit(1)

    print("\n✅ 고급 스트리밍 테스트 완료!")


if __name__ == "__main__":
    main()