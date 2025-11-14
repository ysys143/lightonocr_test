# OCR 스트리밍 vs 일반 처리 비교

## 개요
LightOnOCR 서버는 두 가지 방식의 OCR 처리를 지원합니다:
1. **일반 모드**: 전체 텍스트 처리 완료 후 한 번에 결과 반환
2. **스트리밍 모드**: 텍스트가 생성되는 대로 실시간 반환

## 차이점

### 일반 모드 (`test_ocr.py`)
```bash
python test_ocr.py image.png
```
- 전체 처리가 완료될 때까지 대기
- 결과를 한 번에 받아서 처리
- 메모리에 전체 결과 보관
- 중간에 중단되면 결과 없음

### 스트리밍 모드 (`test_ocr_stream.py`)
```bash
python test_ocr_stream.py image.png
```
- 텍스트가 생성되는 즉시 화면에 출력
- 실시간으로 파일에 저장
- 메모리 효율적
- 중간에 중단되어도 그때까지의 결과 보존

## 사용 시나리오

### 스트리밍 모드가 유리한 경우
- 긴 문서 처리 (여러 페이지 PDF)
- 실시간 피드백이 필요한 경우
- 메모리가 제한적인 환경
- 네트워크가 불안정한 환경

### 일반 모드가 유리한 경우
- 짧은 텍스트 처리
- 후처리가 필요한 경우
- 전체 텍스트를 한 번에 분석해야 하는 경우
- API 통합이 필요한 경우

## 구현 차이

### API 요청 차이
```python
# 일반 모드
request_data = {
    "stream": False,  # 또는 생략
    ...
}

# 스트리밍 모드
request_data = {
    "stream": True,
    ...
}
```

### 응답 처리 차이
```python
# 일반 모드
response = httpx.post(API_ENDPOINT, json=request_data)
result = response.json()
text = result["choices"][0]["message"]["content"]

# 스트리밍 모드
with client.stream("POST", API_ENDPOINT, json=request_data) as response:
    for line in response.iter_lines():
        if line.startswith("data: "):
            # Server-Sent Events (SSE) 형식 처리
            data = json.loads(line[6:])
            content = data["choices"][0]["delta"]["content"]
            print(content, end="", flush=True)
```

## 성능 비교

### 사용자 체감
- **스트리밍**: 첫 텍스트까지 ~1초
- **일반**: 전체 완료까지 대기 (5-30초)

### 메모리 사용
- **스트리밍**: 청크 단위 처리 (낮음)
- **일반**: 전체 텍스트 보관 (높음)

### 파일 저장
- **스트리밍**: 실시간 append
- **일반**: 처리 완료 후 한 번에 저장

## 실제 사용 예시

### PDF 파일 처리
```bash
# 11페이지 PDF 처리 시
# 일반 모드: 모든 페이지 처리 후 결과 표시 (약 2분 후)
python test_ocr.py data/test.pdf

# 스트리밍 모드: 각 페이지별로 실시간 표시 (첫 페이지 10초 내)
python test_ocr_stream.py data/test.pdf
```

### 이미지 파일 처리
```bash
# 일반 모드
python test_ocr.py screenshot.png

# 스트리밍 모드 (텍스트가 나타나는 것을 실시간으로 확인)
python test_ocr_stream.py screenshot.png
```

## 기술적 세부사항

### Server-Sent Events (SSE)
llama.cpp 서버는 스트리밍 시 SSE 프로토콜을 사용:
```
data: {"id":"chatcmpl-1","choices":[{"delta":{"content":"Hello"},"index":0}]}
data: {"id":"chatcmpl-1","choices":[{"delta":{"content":" world"},"index":0}]}
data: [DONE]
```

### 청크 크기
- 일반적으로 단어 또는 구문 단위로 스트리밍
- 네트워크 상황에 따라 버퍼링 발생 가능

### 에러 처리
스트리밍 모드에서는 각 청크별로 에러 처리 필요:
```python
try:
    json_data = json.loads(data)
except json.JSONDecodeError:
    continue  # 잘못된 청크 무시
```

## 결론
- 대부분의 경우 **스트리밍 모드**가 더 나은 사용자 경험 제공
- 특히 긴 문서나 PDF 처리 시 스트리밍이 유리
- API 통합이나 자동화된 워크플로우에는 일반 모드가 적합