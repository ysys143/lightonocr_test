#!/usr/bin/env python3
"""
LightOnOCR 통합 클라이언트
실시간 스트리밍을 기본으로 하는 OCR 처리 도구
"""

import base64
import json
import sys
import time
from pathlib import Path
from typing import Iterator, Optional, Literal
from enum import Enum
import argparse
import io
import os

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


def perform_ocr(
    image_base64: str,
    prompt: str = "Extract all text from this image.",
    output_file: Optional[Path] = None,
    stream: bool = True,
    save_mode: SaveMode = SaveMode.TOKEN,
    quiet: bool = False,
    show_stats: bool = False
) -> str:
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
        "stream": stream
    }

    # 통계 변수
    stats = {
        "tokens": 0,
        "saves": 0,
        "start_time": time.time(),
        "first_token_time": None
    }

    if not stream:
        # 비스트리밍 모드
        try:
            response = httpx.post(API_ENDPOINT, json=request_data, timeout=60)
            if response.status_code == 200:
                result = response.json()
                if "choices" in result and len(result["choices"]) > 0:
                    text = result["choices"][0]["message"]["content"]

                    if not quiet:
                        print(text)

                    if output_file:
                        with open(output_file, "a", encoding="utf-8") as f:
                            f.write(text)

                    return text
            else:
                print(f"❌ API 오류: {response.status_code}")
                return ""
        except Exception as e:
            print(f"❌ OCR 처리 중 오류: {e}")
            return ""

    # 스트리밍 모드
    file_handle = None
    if output_file:
        buffering = 0 if save_mode == SaveMode.TOKEN else 1
        file_handle = open(output_file, "a", encoding="utf-8", buffering=buffering)

    total_text = ""
    try:
        buffer = ""
        with httpx.Client(timeout=120) as client:
            with client.stream("POST", API_ENDPOINT, json=request_data) as response:
                if response.status_code != 200:
                    print(f"❌ API 오류: {response.status_code}")
                    return ""

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
                                    total_text += content

                                    # 화면 출력
                                    if not quiet:
                                        print(content, end="", flush=True)

                                    # 저장 모드에 따른 처리
                                    if save_mode == SaveMode.TOKEN:
                                        # 즉시 저장
                                        if file_handle:
                                            file_handle.write(content)
                                            file_handle.flush()
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

    return total_text


def process_image_file(
    image_path: Path,
    stream: bool = True,
    save_mode: SaveMode = SaveMode.TOKEN,
    quiet: bool = False,
    show_stats: bool = False,
    no_save: bool = False
):
    """이미지 파일을 처리합니다."""
    mode_str = f"스트리밍 - {save_mode.value}" if stream else "일반"
    if not quiet:
        print(f"\n🖼️ 이미지 처리 ({mode_str} 모드): {image_path.name}")
        print("-" * 40)

    if not image_path.exists():
        print(f"❌ 파일을 찾을 수 없습니다: {image_path}")
        return

    # 출력 파일 경로
    output_path = None
    if not no_save:
        if stream and save_mode != SaveMode.TOKEN:
            output_path = image_path.with_suffix(f".{save_mode.value}.md")
        else:
            output_path = image_path.with_suffix(".md")

        # 파일 초기화
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(f"# OCR 결과: {image_path.name}\n\n")
            f.write(f"**처리 방식**: {mode_str}\n\n")
            f.write("---\n\n")

        if not quiet:
            print(f"📝 결과 파일: {output_path}")

    if not quiet:
        print(f"🔍 OCR 처리 중...")
        if stream:
            print("=" * 50)

    # 이미지를 base64로 변환
    start_time = time.time()
    image_base64 = image_to_base64(image_path)

    # OCR 수행
    extracted_text = perform_ocr(
        image_base64,
        output_file=output_path,
        stream=stream,
        save_mode=save_mode,
        quiet=quiet,
        show_stats=show_stats
    )

    elapsed_time = time.time() - start_time

    if stream and not quiet:
        print("\n" + "=" * 50)

    # 처리 시간 추가
    if output_path:
        with open(output_path, "a", encoding="utf-8") as f:
            f.write(f"\n\n---\n\n**처리 시간**: {elapsed_time:.2f}초\n")

    if extracted_text:
        if not quiet:
            print(f"\n✅ 텍스트 추출 완료 ({elapsed_time:.2f}초)")
            if output_path:
                print(f"💾 저장 완료: {output_path}")
    else:
        print("❌ 텍스트 추출 실패")


def process_pdf_file(
    pdf_path: Path,
    stream: bool = True,
    save_mode: SaveMode = SaveMode.TOKEN,
    quiet: bool = False,
    show_stats: bool = False,
    no_save: bool = False
):
    """PDF 파일을 처리합니다."""
    mode_str = f"스트리밍 - {save_mode.value}" if stream else "일반"
    if not quiet:
        print(f"\n📄 PDF 처리 ({mode_str} 모드): {pdf_path.name}")
        print("-" * 40)

    if not pdf_path.exists():
        print(f"❌ 파일을 찾을 수 없습니다: {pdf_path}")
        return

    # PDF를 이미지로 변환
    images = pdf_to_images(pdf_path)
    if not images:
        return

    # 출력 파일 경로
    output_path = None
    if not no_save:
        if stream and save_mode != SaveMode.TOKEN:
            output_path = pdf_path.with_suffix(f".{save_mode.value}.md")
        else:
            output_path = pdf_path.with_suffix(".md")

        # 파일 초기화
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(f"# OCR 결과: {pdf_path.name}\n\n")
            f.write(f"**총 페이지 수**: {len(images)}페이지\n")
            f.write(f"**처리 방식**: {mode_str}\n\n")
            f.write("---\n\n")

        if not quiet:
            print(f"📝 결과 파일: {output_path}")

    total_start_time = time.time()
    success_count = 0

    # 각 페이지 처리
    for i, image in enumerate(images, 1):
        if not quiet:
            print(f"\n📖 페이지 {i}/{len(images)} 처리 중...")
            if stream:
                print("-" * 40)

        try:
            # PIL Image를 base64로 변환
            buffer = io.BytesIO()
            image.save(buffer, format="JPEG", quality=95)
            image_base64 = base64.b64encode(buffer.getvalue()).decode()

            # 페이지 헤더 추가
            if output_path:
                with open(output_path, "a", encoding="utf-8") as f:
                    f.write(f"## 페이지 {i}\n\n")

            # OCR 수행
            extracted_text = perform_ocr(
                image_base64,
                f"Extract all text from page {i} of this document.",
                output_file=output_path,
                stream=stream,
                save_mode=save_mode,
                quiet=quiet,
                show_stats=False  # 페이지별 통계는 표시하지 않음
            )

            if extracted_text:
                success_count += 1
                if not quiet:
                    print(f"\n✅ 페이지 {i} 완료")
            else:
                if not quiet:
                    print(f"\n⚠️ 페이지 {i} 텍스트 추출 실패")
                if output_path:
                    with open(output_path, "a", encoding="utf-8") as f:
                        f.write("*[텍스트 추출 실패]*\n")

            # 페이지 구분자 추가
            if output_path and i < len(images):
                with open(output_path, "a", encoding="utf-8") as f:
                    f.write("\n\n---\n\n")

        except Exception as e:
            print(f"\n❌ 페이지 {i} 처리 중 오류: {e}")
            if output_path:
                with open(output_path, "a", encoding="utf-8") as f:
                    f.write(f"*[처리 오류: {str(e)}]*\n\n")
                    if i < len(images):
                        f.write("---\n\n")

    total_elapsed = time.time() - total_start_time

    # 마지막에 처리 시간 추가
    if output_path:
        with open(output_path, "a", encoding="utf-8") as f:
            f.write(f"\n---\n\n**전체 처리 시간**: {total_elapsed:.2f}초\n")

    if not quiet:
        print(f"\n✅ 전체 PDF 처리 완료 ({total_elapsed:.2f}초)")
        print(f"   성공: {success_count}/{len(images)} 페이지")
        if output_path:
            print(f"💾 저장 완료: {output_path}")

    if show_stats:
        print(f"\n📊 처리 통계:")
        print(f"   총 페이지: {len(images)}")
        print(f"   성공한 페이지: {success_count}")
        print(f"   평균 페이지 처리 시간: {total_elapsed/len(images):.2f}초")


def main():
    """메인 함수"""
    parser = argparse.ArgumentParser(
        description="LightOnOCR - llama.cpp 기반 OCR 클라이언트",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
예제:
  기본 사용 (스트리밍):
    python ocr.py image.png
    python ocr.py document.pdf

  비스트리밍 모드:
    python ocr.py --no-stream image.png

  저장 모드 변경:
    python ocr.py --save-mode sentence document.jpg
    python ocr.py -m paragraph long_document.pdf

  조용한 모드:
    python ocr.py --quiet image.png

  통계 표시:
    python ocr.py --stats document.pdf

  파일 저장 안 함:
    python ocr.py --no-save image.png
        """
    )

    parser.add_argument('file', type=str, nargs='?',
                       help='처리할 파일 경로 (이미지 또는 PDF)')

    parser.add_argument('--no-stream', action='store_true',
                       help='비스트리밍 모드 사용 (기본: 스트리밍)')

    parser.add_argument('-m', '--save-mode', type=str,
                       choices=[m.value for m in SaveMode],
                       default=SaveMode.TOKEN.value,
                       help=f'파일 저장 모드 (기본: {SaveMode.TOKEN.value})')

    parser.add_argument('-q', '--quiet', action='store_true',
                       help='조용한 모드 (텍스트 출력 안 함)')

    parser.add_argument('--stats', action='store_true',
                       help='처리 통계 표시')

    parser.add_argument('--no-save', action='store_true',
                       help='파일로 저장하지 않음')

    parser.add_argument('--server', type=str, default=SERVER_URL,
                       help=f'서버 URL (기본: {SERVER_URL})')

    args = parser.parse_args()

    # 전역 서버 URL 업데이트
    if args.server != SERVER_URL:
        global SERVER_URL, API_ENDPOINT, HEALTH_ENDPOINT
        SERVER_URL = args.server
        API_ENDPOINT = f"{SERVER_URL}/v1/chat/completions"
        HEALTH_ENDPOINT = f"{SERVER_URL}/health"

    print("=" * 50)
    print("   LightOnOCR - 통합 OCR 클라이언트")
    print("=" * 50)

    # 서버 상태 확인
    if not check_server_health():
        sys.exit(1)

    # 파일 경로 확인
    if not args.file:
        # 기본 테스트 파일 찾기
        test_files = [
            Path("data/test.pdf"),
            Path("data/test_images/sample.png"),
            Path("data/test_images/sample.jpg")
        ]

        file_path = None
        for f in test_files:
            if f.exists():
                file_path = f
                print(f"\n테스트 파일 사용: {file_path}")
                break

        if not file_path:
            print("\n❌ 파일 경로를 지정하거나 테스트 파일을 준비해주세요")
            parser.print_help()
            sys.exit(1)
    else:
        file_path = Path(args.file)

    # SaveMode 변환
    save_mode = SaveMode(args.save_mode)

    # 설정 표시
    if not args.quiet:
        print(f"\n⚙️ 설정:")
        print(f"   스트리밍: {'비활성화' if args.no_stream else '활성화'}")
        if not args.no_stream:
            print(f"   저장 모드: {save_mode.value}")
        print(f"   파일 저장: {'비활성화' if args.no_save else '활성화'}")
        print(f"   통계 표시: {'활성화' if args.stats else '비활성화'}")

    # 파일 처리
    if file_path.suffix.lower() == ".pdf":
        process_pdf_file(
            file_path,
            stream=not args.no_stream,
            save_mode=save_mode,
            quiet=args.quiet,
            show_stats=args.stats,
            no_save=args.no_save
        )
    elif file_path.suffix.lower() in [".png", ".jpg", ".jpeg", ".bmp", ".gif", ".tiff"]:
        process_image_file(
            file_path,
            stream=not args.no_stream,
            save_mode=save_mode,
            quiet=args.quiet,
            show_stats=args.stats,
            no_save=args.no_save
        )
    else:
        print(f"❌ 지원하지 않는 파일 형식: {file_path.suffix}")
        print("   지원 형식: PDF, PNG, JPG, JPEG, BMP, GIF, TIFF")
        sys.exit(1)

    if not args.quiet:
        print("\n✅ OCR 처리 완료!")


if __name__ == "__main__":
    main()