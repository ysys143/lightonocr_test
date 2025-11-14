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
from typing import Iterator, Optional, Literal, Dict, Any
from enum import Enum
import argparse
import io
import os
import pickle
from dataclasses import dataclass, field
from datetime import datetime
from difflib import SequenceMatcher

import httpx
from PIL import Image
from pdf2image import convert_from_path

try:
    import yaml
except ImportError:
    yaml = None
    print("⚠️ PyYAML이 설치되지 않았습니다. YAML 설정 파일을 사용하려면 설치하세요:")
    print("   uv pip install pyyaml")

# 서버 설정
SERVER_URL = "http://localhost:8080"
API_ENDPOINT = f"{SERVER_URL}/v1/chat/completions"
HEALTH_ENDPOINT = f"{SERVER_URL}/health"
MODEL_NAME = "LightOnOCR-1B-1025"

# 기본 설정 파일 경로
DEFAULT_CONFIG_FILES = [
    Path("ocr_config.yml"),
    Path("ocr_config.yaml"),
    Path(".ocr_config.yml"),
    Path(".ocr_config.yaml"),
    Path.home() / ".config" / "lightonocr" / "config.yml",
]


class SaveMode(Enum):
    """파일 저장 모드"""
    TOKEN = "token"          # 매 토큰마다 저장 (가장 빠름)
    WORD = "word"           # 단어 단위로 저장
    SENTENCE = "sentence"    # 문장 단위로 저장
    PARAGRAPH = "paragraph"  # 문단 단위로 저장
    LINE = "line"           # 줄 단위로 저장


# 예외 클래스들
class RepetitionError(Exception):
    """반복 패턴 감지 시 발생하는 예외"""
    pass


class PageTimeoutError(TimeoutError):
    """페이지 타임아웃 시 발생하는 예외"""
    pass


class TokenLimitError(Exception):
    """토큰 수 제한 초과 시 발생하는 예외"""
    pass


class APIError(Exception):
    """API 요청 실패 시 발생하는 예외"""
    pass


def load_config_file(config_path: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    """YAML 설정 파일을 로드합니다."""
    if yaml is None:
        return None

    # 지정된 설정 파일 경로가 있으면 사용
    if config_path:
        if config_path.exists():
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = yaml.safe_load(f)
                    print(f"✅ 설정 파일 로드: {config_path}")
                    return config
            except Exception as e:
                print(f"⚠️ 설정 파일 로드 실패: {e}")
                return None
        else:
            print(f"❌ 설정 파일을 찾을 수 없습니다: {config_path}")
            return None

    # 기본 설정 파일 위치에서 찾기
    for default_path in DEFAULT_CONFIG_FILES:
        if default_path.exists():
            try:
                with open(default_path, 'r', encoding='utf-8') as f:
                    config = yaml.safe_load(f)
                    print(f"✅ 설정 파일 로드: {default_path}")
                    return config
            except Exception as e:
                continue

    return None


def create_default_config(config_path: Path) -> bool:
    """기본 설정 파일을 생성합니다."""
    default_config = {
        'server': {
            'url': 'http://localhost:8080',
            'model': 'LightOnOCR-1B-1025',
            'timeout': 120
        },
        'ocr': {
            'streaming': True,
            'save_mode': 'token',
            'save_file': True,
            'quiet': False,
            'show_stats': False
        },
        'pdf': {
            'skip_errors': False,
            'max_retries': 2,
            'page_timeout': 120.0,
            'max_page_tokens': 8000,
            'dpi': 200
        },
        'image': {
            'jpeg_quality': 95,
            'supported_formats': ['.png', '.jpg', '.jpeg', '.bmp', '.gif', '.tiff']
        },
        'advanced': {
            'repetition_detection': {
                'enabled': True,
                'window_size': 50,
                'threshold': 0.8,
                'max_normal_reps': 5
            },
            'api': {
                'temperature': 0.1,
                'max_tokens': 4096
            }
        },
        'output': {
            'include_headers': True,
            'include_separators': True,
            'include_timing': True
        },
        'debug': {
            'enabled': False,
            'log_api_calls': False
        }
    }

    try:
        # 디렉토리 생성
        config_path.parent.mkdir(parents=True, exist_ok=True)

        if yaml:
            with open(config_path, 'w', encoding='utf-8') as f:
                yaml.dump(default_config, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
            print(f"✅ 기본 설정 파일 생성: {config_path}")
            return True
        else:
            print("⚠️ PyYAML이 설치되지 않아 설정 파일을 생성할 수 없습니다")
            return False
    except Exception as e:
        print(f"❌ 설정 파일 생성 실패: {e}")
        return False


def merge_config_with_args(config: Dict[str, Any], args: argparse.Namespace) -> argparse.Namespace:
    """YAML 설정과 명령줄 인자를 병합합니다. 명령줄 인자가 우선순위를 가집니다."""
    # 설정 값을 args에 적용 (명령줄에서 지정되지 않은 경우만)

    # 서버 설정
    if 'server' in config:
        if not args.server:
            args.server = config['server'].get('url', SERVER_URL)

    # OCR 설정
    if 'ocr' in config:
        ocr = config['ocr']
        # no_stream은 반대 논리
        if not hasattr(args, 'no_stream') or args.no_stream is False:
            args.no_stream = not ocr.get('streaming', True)

        if not args.save_mode or args.save_mode == SaveMode.TOKEN.value:
            args.save_mode = ocr.get('save_mode', SaveMode.TOKEN.value)

        if not args.quiet:
            args.quiet = ocr.get('quiet', False)

        if not args.stats:
            args.stats = ocr.get('show_stats', False)

        if not args.no_save:
            args.no_save = not ocr.get('save_file', True)

    # PDF 설정
    if 'pdf' in config:
        pdf = config['pdf']
        if not args.skip_errors:
            args.skip_errors = pdf.get('skip_errors', False)

        if args.max_retries == 2:  # 기본값인 경우만
            args.max_retries = pdf.get('max_retries', 2)

        if args.page_timeout == 120.0:  # 기본값인 경우만
            args.page_timeout = pdf.get('page_timeout', 120.0)

        if args.max_page_tokens == 8000:  # 기본값인 경우만
            args.max_page_tokens = pdf.get('max_page_tokens', 8000)

    return args


class RepetitionDetector:
    """토큰 반복 패턴 감지기"""

    def __init__(self,
                 window_size: int = 50,
                 threshold: float = 0.8,
                 max_normal_reps: int = 5):
        """
        Args:
            window_size: 비교할 토큰 윈도우 크기
            threshold: 반복 판정 유사도 임계값 (0.0-1.0)
            max_normal_reps: 정상 반복 최대 횟수
        """
        self.window_size = window_size
        self.threshold = threshold
        self.max_normal_reps = max_normal_reps
        self.buffer = []
        self.consecutive_reps = 0

    def add_token(self, token: str) -> bool:
        """
        토큰 추가 및 반복 감지

        Returns:
            True if repetition detected (should stop)
        """
        self.buffer.append(token)

        # 버퍼가 충분히 차면 분석
        if len(self.buffer) >= self.window_size * 2:
            recent = ''.join(self.buffer[-self.window_size:])
            previous = ''.join(self.buffer[-self.window_size*2:-self.window_size])

            # 유사도 계산
            similarity = self._calculate_similarity(recent, previous)

            if similarity > self.threshold:
                self.consecutive_reps += 1

                # 연속 반복이 허용 횟수 초과
                if self.consecutive_reps > self.max_normal_reps:
                    return True
            else:
                # 반복이 끊기면 카운터 리셋
                self.consecutive_reps = 0

            # 버퍼 크기 제한 (메모리 관리)
            if len(self.buffer) > self.window_size * 3:
                self.buffer = self.buffer[-self.window_size*2:]

        return False

    def _calculate_similarity(self, s1: str, s2: str) -> float:
        """두 문자열의 유사도 계산"""
        if s1 == s2:
            return 1.0
        # SequenceMatcher를 사용한 유사도 계산
        return SequenceMatcher(None, s1, s2).ratio()

    def reset(self):
        """버퍼와 카운터 리셋"""
        self.buffer = []
        self.consecutive_reps = 0


@dataclass
class PDFProgress:
    """PDF 처리 진행 상황"""
    pdf_path: str
    total_pages: int
    completed_pages: set[int] = field(default_factory=set)
    failed_pages: dict[int, str] = field(default_factory=dict)  # {페이지번호: 에러메시지}
    skipped_pages: set[int] = field(default_factory=set)
    last_update: datetime = field(default_factory=datetime.now)

    def save(self, progress_file: Path):
        """진행 상황 저장"""
        try:
            with open(progress_file, 'wb') as f:
                pickle.dump(self, f)
        except Exception as e:
            print(f"⚠️ 진행 상황 저장 실패: {e}")

    @classmethod
    def load(cls, progress_file: Path) -> Optional['PDFProgress']:
        """진행 상황 로드"""
        if not progress_file.exists():
            return None
        try:
            with open(progress_file, 'rb') as f:
                return pickle.load(f)
        except Exception as e:
            print(f"⚠️ 진행 상황 로드 실패: {e}")
            return None

    def get_pending_pages(self) -> list[int]:
        """아직 처리되지 않은 페이지 목록"""
        all_pages = set(range(1, self.total_pages + 1))
        pending = all_pages - self.completed_pages - self.skipped_pages
        return sorted(pending)

    def is_complete(self) -> bool:
        """모든 페이지 처리 완료 여부"""
        return len(self.completed_pages) + len(self.skipped_pages) >= self.total_pages


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
    prompt: str = "Perform OCR on this image and extract all visible text accurately. Preserve the original structure, formatting, and layout as much as possible. Include headings, paragraphs, lists, tables, equations, and any other textual content. For figures, diagrams, charts, or images, describe their position (e.g., 'top-left', 'center', 'bottom-right'), their relationship to surrounding text, and provide a brief description of what they depict. Use markdown format with placeholders like '![Figure X: description](position)' for visual elements. Maintain the spatial hierarchy and reading order of the document.",
    output_file: Optional[Path] = None,
    stream: bool = True,
    save_mode: SaveMode = SaveMode.TOKEN,
    quiet: bool = False,
    show_stats: bool = False,
    page_timeout: Optional[float] = None,
    max_page_tokens: Optional[int] = None
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
                if not quiet:
                    print(f"❌ API 오류: {response.status_code}")
                raise APIError(f"API error: {response.status_code}")
        except APIError:
            raise
        except Exception as e:
            print(f"❌ OCR 처리 중 오류: {e}")
            raise APIError(f"OCR processing error: {e}")

    # 스트리밍 모드
    file_handle = None
    if output_file:
        # Python 3에서는 텍스트 모드에서 unbuffered(0)를 사용할 수 없음
        # 최소 line buffered(1) 사용하고, TOKEN 모드에서는 flush()와 fsync()로 즉시 저장
        file_handle = open(output_file, "a", encoding="utf-8", buffering=1)

    # 반복 감지기 초기화
    repetition_detector = RepetitionDetector()

    total_text = ""
    try:
        buffer = ""
        # 타임아웃 설정 (기본값: 120초, 페이지 타임아웃이 있으면 그것 사용)
        timeout = page_timeout if page_timeout else 120
        with httpx.Client(timeout=timeout) as client:
            with client.stream("POST", API_ENDPOINT, json=request_data) as response:
                if response.status_code != 200:
                    if not quiet:
                        print(f"❌ API 오류: {response.status_code}")
                    raise APIError(f"API error: {response.status_code}")

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
                                    # 타임아웃 체크
                                    if page_timeout and (time.time() - stats["start_time"]) > page_timeout:
                                        if not quiet:
                                            print(f"\n\n⏱️ 페이지 타임아웃 ({page_timeout}초 초과)")
                                        raise PageTimeoutError(f"Page timeout after {page_timeout} seconds")

                                    # 토큰 수 체크
                                    if max_page_tokens and stats["tokens"] >= max_page_tokens:
                                        if not quiet:
                                            print(f"\n\n🛑 최대 토큰 수 도달 ({max_page_tokens})")
                                        raise TokenLimitError(f"Token limit reached: {max_page_tokens}")

                                    # 반복 감지
                                    if repetition_detector.add_token(content):
                                        if not quiet:
                                            print(f"\n\n⚠️ 반복 패턴 감지! ({repetition_detector.consecutive_reps}회 연속 {int(repetition_detector.threshold*100)}% 유사)")
                                        raise RepetitionError(f"Repetition pattern detected after {repetition_detector.consecutive_reps} consecutive repetitions")

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

    except (RepetitionError, PageTimeoutError, TokenLimitError, APIError) as e:
        # 우리가 정의한 예외들은 그대로 전파
        if not quiet:
            print(f"\n🛑 처리 중단: {e}")
        raise
    except httpx.TimeoutException:
        if not quiet:
            print("\n⏱️ 요청 시간 초과")
        raise APIError("Request timeout")
    except Exception as e:
        if not quiet:
            print(f"\n❌ OCR 처리 중 오류: {e}")
        raise APIError(f"Unexpected error: {e}")
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
    try:
        extracted_text = perform_ocr(
            image_base64,
            output_file=output_path,
            stream=stream,
            save_mode=save_mode,
            quiet=quiet,
            show_stats=show_stats
        )
    except (RepetitionError, PageTimeoutError, TokenLimitError) as e:
        if not quiet:
            print(f"\n⚠️ 처리 중단: {e}")
        # 부분 결과라도 저장
        if output_path:
            with open(output_path, "a", encoding="utf-8") as f:
                f.write(f"\n\n*[처리 중단: {e}]*\n")
        extracted_text = None
    except APIError as e:
        if not quiet:
            print(f"\n❌ API 오류: {e}")
        if output_path:
            with open(output_path, "a", encoding="utf-8") as f:
                f.write(f"\n\n*[API 오류: {e}]*\n")
        extracted_text = None

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
        if not quiet:
            print(f"\n⚠️ 텍스트 추출 실패 또는 중단 ({elapsed_time:.2f}초)")
            if output_path:
                print(f"💾 부분 결과 저장: {output_path}")


def process_pdf_file(
    pdf_path: Path,
    stream: bool = True,
    save_mode: SaveMode = SaveMode.TOKEN,
    quiet: bool = False,
    show_stats: bool = False,
    no_save: bool = False,
    resume: bool = False,
    start_page: Optional[int] = None,
    skip_errors: bool = False,
    max_retries: int = 2,
    page_timeout: Optional[float] = 120.0,
    max_page_tokens: Optional[int] = 8000
):
    """PDF 파일을 처리합니다."""
    mode_str = f"스트리밍 - {save_mode.value}" if stream else "일반"
    if not quiet:
        print(f"\n📄 PDF 처리 ({mode_str} 모드): {pdf_path.name}")
        print("-" * 40)

    if not pdf_path.exists():
        print(f"❌ 파일을 찾을 수 없습니다: {pdf_path}")
        return

    # 진행 상황 파일 경로
    progress_file = pdf_path.with_suffix('.progress')

    # 진행 상황 로드 또는 초기화
    progress = None
    if resume:
        progress = PDFProgress.load(progress_file)
        if progress and progress.pdf_path == str(pdf_path):
            if not quiet:
                print(f"📂 이전 진행 상황 복원: {len(progress.completed_pages)}/{progress.total_pages} 페이지 완료")
        else:
            if not quiet:
                print("⚠️ 이전 진행 상황을 찾을 수 없습니다. 처음부터 시작합니다.")
            progress = None

    # PDF를 이미지로 변환
    images = pdf_to_images(pdf_path)
    if not images:
        return

    # 진행 상황 초기화 (필요 시)
    if progress is None:
        progress = PDFProgress(
            pdf_path=str(pdf_path),
            total_pages=len(images)
        )

    # 처리할 페이지 결정
    if start_page:
        pages_to_process = list(range(start_page, len(images) + 1))
    else:
        pages_to_process = progress.get_pending_pages()
        if not pages_to_process and not quiet:
            print("✅ 모든 페이지가 이미 처리되었습니다.")
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
    for page_num in pages_to_process:
        # 이미 완료된 페이지는 건너뛰기
        if page_num in progress.completed_pages:
            if not quiet:
                print(f"\n✅ 페이지 {page_num} 이미 완료됨 (건너뜀)")
            success_count += 1
            continue

        if not quiet:
            print(f"\n📖 페이지 {page_num}/{len(images)} 처리 중...")
            if stream:
                print("-" * 40)

        # 페이지 이미지 가져오기
        image = images[page_num - 1]

        retry_count = 0
        page_success = False

        while retry_count < max_retries and not page_success:
            try:
                if retry_count > 0 and not quiet:
                    print(f"🔄 페이지 {page_num} 재시도 ({retry_count}/{max_retries})")

                # PIL Image를 base64로 변환
                buffer = io.BytesIO()
                image.save(buffer, format="JPEG", quality=95)
                image_base64 = base64.b64encode(buffer.getvalue()).decode()

                # 페이지 헤더 추가 (첫 시도일 때만)
                if output_path and retry_count == 0:
                    with open(output_path, "a", encoding="utf-8") as f:
                        f.write(f"## 페이지 {page_num}\n\n")

                # OCR 수행
                extracted_text = perform_ocr(
                    image_base64,
                    f"Perform OCR on page {page_num} of this document. Extract all visible text accurately while preserving the original structure, formatting, and layout. Include headings, paragraphs, lists, tables, equations, citations, and any other textual content. For figures, diagrams, charts, or images, describe their position (e.g., 'top-left', 'center', 'bottom-right'), their relationship to surrounding text, and provide a brief description of what they depict. Use markdown format with placeholders like '![Figure X: description](position)' for visual elements. Maintain the spatial hierarchy and reading order of the document.",
                    output_file=output_path,
                    stream=stream,
                    save_mode=save_mode,
                    quiet=quiet,
                    show_stats=False,  # 페이지별 통계는 표시하지 않음
                    page_timeout=page_timeout,
                    max_page_tokens=max_page_tokens
                )

                if extracted_text:
                    progress.completed_pages.add(page_num)
                    page_success = True
                    success_count += 1
                    if not quiet:
                        print(f"\n✅ 페이지 {page_num} 완료")

            except APIError as e:
                error_msg = str(e)
                retry_count += 1
                if not quiet:
                    print(f"\n❌ API 오류: {error_msg}")

                if retry_count >= max_retries:
                    progress.failed_pages[page_num] = error_msg
                    if skip_errors:
                        progress.skipped_pages.add(page_num)
                        if output_path:
                            with open(output_path, "a", encoding="utf-8") as f:
                                f.write(f"*[API 오류: {error_msg}]*\n")
                        if not quiet:
                            print(f"⏭️ 페이지 {page_num} 건너뜀")
                        break
                    else:
                        if not quiet:
                            print(f"\n❌ 페이지 {page_num} 최대 재시도 횟수 초과")
                        progress.save(progress_file)
                        return

            except (RepetitionError, PageTimeoutError, TokenLimitError) as e:
                error_msg = str(e)
                if not quiet:
                    print(f"\n⚠️ 페이지 {page_num}: {error_msg}")

                if skip_errors:
                    progress.skipped_pages.add(page_num)
                    progress.failed_pages[page_num] = error_msg
                    if output_path:
                        with open(output_path, "a", encoding="utf-8") as f:
                            f.write(f"*[{error_msg}]*\n")
                    if not quiet:
                        print(f"⏭️ 페이지 {page_num} 건너뜀")
                    break
                else:
                    retry_count += 1
                    if retry_count >= max_retries:
                        progress.failed_pages[page_num] = error_msg
                        if not quiet:
                            print(f"\n❌ 페이지 {page_num} 최대 재시도 횟수 초과")
                        # skip_errors가 False면 여기서 전체 중단
                        progress.save(progress_file)
                        return

            except Exception as e:
                error_msg = str(e)
                print(f"\n❌ 페이지 {page_num} 처리 중 예상치 못한 오류: {e}")
                retry_count += 1
                progress.failed_pages[page_num] = error_msg
                if retry_count >= max_retries:
                    if output_path:
                        with open(output_path, "a", encoding="utf-8") as f:
                            f.write(f"*[처리 오류: {error_msg}]*\n")
                    if skip_errors:
                        progress.skipped_pages.add(page_num)
                        break
                    else:
                        progress.save(progress_file)
                        return

        # 페이지 구분자 추가
        if output_path and page_num < len(images):
            with open(output_path, "a", encoding="utf-8") as f:
                f.write("\n\n---\n\n")

        # 진행 상황 저장 (페이지마다)
        progress.last_update = datetime.now()
        progress.save(progress_file)

    total_elapsed = time.time() - total_start_time

    # 마지막에 처리 시간 추가
    if output_path:
        with open(output_path, "a", encoding="utf-8") as f:
            f.write(f"\n---\n\n**전체 처리 시간**: {total_elapsed:.2f}초\n")

    # 완료 시 진행 상황 파일 처리
    if progress.is_complete():
        progress_file.unlink(missing_ok=True)
        if not quiet:
            print(f"🗑️ 진행 상황 파일 삭제 (모든 페이지 완료)")

    if not quiet:
        print(f"\n✅ 전체 PDF 처리 완료 ({total_elapsed:.2f}초)")
        print(f"   성공: {success_count}/{len(images)} 페이지")
        if len(progress.skipped_pages) > 0:
            print(f"   건너뜀: {len(progress.skipped_pages)} 페이지")
        if len(progress.failed_pages) > 0:
            print(f"   실패: {len(progress.failed_pages)} 페이지")
        if output_path:
            print(f"💾 저장 완료: {output_path}")

    if show_stats:
        print(f"\n📊 처리 통계:")
        print(f"   총 페이지: {len(images)}")
        print(f"   성공한 페이지: {success_count}")
        print(f"   평균 페이지 처리 시간: {total_elapsed/len(images):.2f}초")


def main():
    """메인 함수"""
    global SERVER_URL, API_ENDPOINT, HEALTH_ENDPOINT

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

    # 새로운 인자들 추가
    parser.add_argument('--resume', action='store_true',
                       help='중단된 위치부터 재시작 (.progress 파일 사용)')

    parser.add_argument('--start-page', type=int, metavar='N',
                       help='특정 페이지부터 시작 (1부터 시작)')

    parser.add_argument('--skip-errors', action='store_true',
                       help='문제 페이지 건너뛰고 계속 진행')

    parser.add_argument('--max-retries', type=int, default=2, metavar='N',
                       help='페이지당 최대 재시도 횟수 (기본: 2)')

    parser.add_argument('--page-timeout', type=float, default=120.0, metavar='SECONDS',
                       help='페이지당 최대 처리 시간 (초, 기본: 120)')

    parser.add_argument('--max-page-tokens', type=int, default=8000, metavar='N',
                       help='페이지당 최대 토큰 수 (기본: 8000)')

    # 설정 파일 관련 인자
    parser.add_argument('-c', '--config', type=str, metavar='FILE',
                       help='YAML 설정 파일 경로')

    parser.add_argument('--create-config', type=str, metavar='FILE',
                       help='기본 설정 파일 생성')

    parser.add_argument('--no-config', action='store_true',
                       help='설정 파일을 사용하지 않음')

    args = parser.parse_args()

    # 설정 파일 생성 요청 처리
    if args.create_config:
        config_path = Path(args.create_config)
        if create_default_config(config_path):
            print(f"🎉 설정 파일이 생성되었습니다: {config_path}")
            print("   필요에 따라 파일을 수정한 후 사용하세요.")
        sys.exit(0)

    # 설정 파일 로드 및 병합
    if not args.no_config:
        if args.config:
            # 명시적으로 지정된 설정 파일
            config_path = Path(args.config)
            config = load_config_file(config_path)
        else:
            # 기본 위치에서 설정 파일 찾기
            config = load_config_file()

        if config:
            args = merge_config_with_args(config, args)

    # 전역 서버 URL 업데이트
    if args.server != SERVER_URL:
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
            no_save=args.no_save,
            resume=args.resume,
            start_page=args.start_page,
            skip_errors=args.skip_errors,
            max_retries=args.max_retries,
            page_timeout=args.page_timeout,
            max_page_tokens=args.max_page_tokens
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