# API 문서

LightOnOCR는 OpenAI Chat Completions API와 호환되는 REST API를 제공합니다.

## 엔드포인트

### 기본 URL
```
http://localhost:8080
```

### 주요 엔드포인트

| 엔드포인트 | 메서드 | 설명 |
|-----------|--------|------|
| `/health` | GET | 서버 상태 확인 |
| `/v1/models` | GET | 사용 가능한 모델 목록 |
| `/v1/chat/completions` | POST | OCR 요청 |

## 헬스 체크

### 요청
```bash
curl http://localhost:8080/health
```

### 응답
```json
{
  "status": "ok"
}
```

## 모델 정보

### 요청
```bash
curl http://localhost:8080/v1/models
```

### 응답
```json
{
  "data": [
    {
      "id": "LightOnOCR-1B-1025",
      "object": "model",
      "created": 1234567890,
      "owned_by": "lightonai"
    }
  ]
}
```

## OCR 요청

### 요청 형식

```json
{
  "model": "LightOnOCR-1B-1025",
  "messages": [
    {
      "role": "user",
      "content": [
        {
          "type": "text",
          "text": "Extract all text from this image."
        },
        {
          "type": "image_url",
          "image_url": {
            "url": "data:image/jpeg;base64,{BASE64_IMAGE_DATA}"
          }
        }
      ]
    }
  ],
  "temperature": 0.1,
  "max_tokens": 4096,
  "stream": false
}
```

### 파라미터 설명

| 파라미터 | 타입 | 필수 | 설명 | 기본값 |
|---------|------|------|------|--------|
| `model` | string | ✓ | 모델 이름 | - |
| `messages` | array | ✓ | 메시지 배열 | - |
| `temperature` | float | ✗ | 생성 온도 (0.0-1.0) | 0.1 |
| `max_tokens` | integer | ✗ | 최대 생성 토큰 수 | 4096 |
| `stream` | boolean | ✗ | 스트리밍 응답 | false |

### 응답 형식 (비스트리밍)

```json
{
  "id": "chatcmpl-123",
  "object": "chat.completion",
  "created": 1677652288,
  "model": "LightOnOCR-1B-1025",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "추출된 텍스트 내용..."
      },
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "prompt_tokens": 100,
    "completion_tokens": 200,
    "total_tokens": 300
  }
}
```

### 응답 형식 (스트리밍)

```
data: {"id":"chatcmpl-123","object":"chat.completion.chunk","created":1677652288,"model":"LightOnOCR-1B-1025","choices":[{"index":0,"delta":{"content":"텍"}}]}

data: {"id":"chatcmpl-123","object":"chat.completion.chunk","created":1677652288,"model":"LightOnOCR-1B-1025","choices":[{"index":0,"delta":{"content":"스"}}]}

data: {"id":"chatcmpl-123","object":"chat.completion.chunk","created":1677652288,"model":"LightOnOCR-1B-1025","choices":[{"index":0,"delta":{"content":"트"}}]}

data: [DONE]
```

## 클라이언트 예제

### Python (httpx)

```python
import base64
import httpx

def ocr_image(image_path, stream=False):
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
            "max_tokens": 4096,
            "stream": stream
        },
        timeout=120
    )

    if stream:
        # 스트리밍 처리
        for line in response.iter_lines():
            if line.startswith("data: "):
                # 스트리밍 데이터 처리
                pass
    else:
        result = response.json()
        return result["choices"][0]["message"]["content"]
```

### Python (requests)

```python
import base64
import requests

def ocr_image(image_path):
    with open(image_path, "rb") as f:
        image_base64 = base64.b64encode(f.read()).decode()

    response = requests.post(
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

### JavaScript (fetch)

```javascript
async function ocrImage(imagePath) {
    // Node.js에서 이미지 읽기
    const fs = require('fs');
    const imageBuffer = fs.readFileSync(imagePath);
    const imageBase64 = imageBuffer.toString('base64');

    const response = await fetch('http://localhost:8080/v1/chat/completions', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
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

### curl

```bash
# 이미지를 base64로 인코딩
IMAGE_BASE64=$(base64 -i image.jpg)

# API 호출
curl -X POST http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d "{
    \"model\": \"LightOnOCR-1B-1025\",
    \"messages\": [{
      \"role\": \"user\",
      \"content\": [
        {\"type\": \"text\", \"text\": \"Extract all text from this image.\"},
        {\"type\": \"image_url\", \"image_url\": {
          \"url\": \"data:image/jpeg;base64,$IMAGE_BASE64\"
        }}
      ]
    }],
    \"temperature\": 0.1,
    \"max_tokens\": 4096
  }"
```

## 스트리밍 API 사용

### Python 스트리밍 예제

```python
import httpx
import json

def ocr_stream(image_path):
    with open(image_path, "rb") as f:
        image_base64 = base64.b64encode(f.read()).decode()

    with httpx.stream(
        "POST",
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
            "stream": True
        }
    ) as response:
        for line in response.iter_lines():
            if line.startswith("data: "):
                data = line[6:]
                if data == "[DONE]":
                    break

                try:
                    json_data = json.loads(data)
                    content = json_data["choices"][0]["delta"].get("content", "")
                    if content:
                        print(content, end="", flush=True)
                except json.JSONDecodeError:
                    pass
```

## 에러 처리

### 일반적인 에러 응답

```json
{
  "error": {
    "message": "Invalid request format",
    "type": "invalid_request_error",
    "code": 400
  }
}
```

### HTTP 상태 코드

| 코드 | 설명 |
|------|------|
| 200 | 성공 |
| 400 | 잘못된 요청 |
| 404 | 엔드포인트를 찾을 수 없음 |
| 408 | 요청 타임아웃 |
| 413 | 이미지 크기 초과 |
| 500 | 서버 내부 오류 |
| 503 | 서비스 사용 불가 |

## 성능 최적화

### 이미지 크기 최적화

```python
from PIL import Image
import io

def optimize_image(image_path, max_size=(2048, 2048), quality=85):
    img = Image.open(image_path)

    # 크기 조정
    img.thumbnail(max_size, Image.Resampling.LANCZOS)

    # JPEG로 압축
    buffer = io.BytesIO()
    img.save(buffer, format="JPEG", quality=quality, optimize=True)

    return base64.b64encode(buffer.getvalue()).decode()
```

### 배치 처리

```python
async def batch_ocr(image_paths, max_concurrent=3):
    import asyncio
    import aiohttp

    async def process_image(session, image_path):
        with open(image_path, "rb") as f:
            image_base64 = base64.b64encode(f.read()).decode()

        async with session.post(
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
                }]
            }
        ) as response:
            result = await response.json()
            return result["choices"][0]["message"]["content"]

    async with aiohttp.ClientSession() as session:
        tasks = []
        for image_path in image_paths:
            task = process_image(session, image_path)
            tasks.append(task)

            if len(tasks) >= max_concurrent:
                results = await asyncio.gather(*tasks)
                tasks = []
                yield from results

        if tasks:
            results = await asyncio.gather(*tasks)
            yield from results
```

## 제한사항

- 최대 이미지 크기: 10MB
- 최대 동시 연결: 10
- 요청 타임아웃: 120초
- 지원 이미지 형식: JPEG, PNG, BMP, GIF, TIFF