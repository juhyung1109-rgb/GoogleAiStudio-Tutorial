# Gemini 3.5 STT (Speech-to-Text) 코드 라인별 해설

본 문서는 `gemini-35-stt-example.py` 파일의 소스 코드를 라인별(Line-by-Line)로 상세히 설명합니다.

---

## 1. 전체 소스 코드

```python
# To run this code you need to install the following dependencies:
# pip install google-genai

import base64
import os
from google import genai
from google.genai import types


def generate():
    client = genai.Client(
        api_key=os.environ.get("GEMINI_API_KEY"),
    )

    model = "gemini-3.5-transcribe"
    audio_path = "output.wav"
    with open(audio_path, "rb") as f:
        audio_bytes = f.read()

    contents = [
        types.Content(
            role="user",
            parts=[
                types.Part.from_bytes(
                    data=audio_bytes,
                    mime_type="audio/wav",
                ),
            ],
        ),
    ]
    generate_content_config = types.GenerateContentConfig(
        audio_transcription_config=types.AudioTranscriptionConfig(
            word_timestamp=True,
            diarization=True,
        ),
    )

    for chunk in client.models.generate_content_stream(
        model=model,
        contents=contents,
        config=generate_content_config,
    ):
        if text := chunk.text:
            print(text, end="")

if __name__ == "__main__":
    generate()
```

---

## 2. 라인별 상세 설명

### [Line 1 ~ 2] 주석 및 라이브러리 설치 안내
```python
1: # To run this code you need to install the following dependencies:
2: # pip install google-genai
```
- **Line 1~2**: 구글의 차세대 통합 SDK 패키지인 `google-genai`의 설치 명령어를 안내합니다.

### [Line 4 ~ 7] 필요한 모듈 임포트
```python
4: import base64
5: import os
6: from google import genai
7: from google.genai import types
```
- **Line 4 (`import base64`)**: 오디오 및 멀티모달 데이터를 다룰 때 인코딩/디코딩에 사용할 수 있는 파이썬 기본 모듈입니다.
- **Line 5 (`import os`)**: 시스템 환경 변수(API 키 등)를 조회하기 위한 모듈입니다.
- **Line 6 (`from google import genai`)**: Gemini API와 통신하기 위한 최신 Google GenAI SDK를 가져옵니다.
- **Line 7 (`from google.genai import types`)**: API 호출 시 요청 데이터 및 파라미터 구조를 정의하는 데이터 클래스 모음입니다.

### [Line 10 ~ 13] 클라이언트 생성
```python
10: def generate():
11:     client = genai.Client(
12:         api_key=os.environ.get("GEMINI_API_KEY"),
13:     )
```
- **Line 10 (`def generate():`)**: STT 변환을 총괄하는 함수를 정의합니다.
- **Line 11~13 (`client = genai.Client(...)`)**: 환경 변수 `GEMINI_API_KEY`에 저장된 API 키를 읽어와 인증된 GenAI 클라이언트를 인스턴스화합니다.

### [Line 15 ~ 19] 모델 지정 및 오디오 파일 로드
```python
15:     model = "gemini-3.5-transcribe"
16:     audio_path = "output.wav"
17:     with open(audio_path, "rb") as f:
18:         audio_bytes = f.read()
```
- **Line 15 (`model = "gemini-3.5-transcribe"`)**: 음성 인식 및 전사 전용 모델을 지정합니다.
- **Line 16 (`audio_path = "output.wav"`)**: 텍스트로 변환할 대상 음성 파일의 상대 경로입니다.
- **Line 17~18 (`with open(...) as f: audio_bytes = f.read()`)**: WAV 오디오 파일을 바이너리 읽기(`rb`) 모드로 열어 파일 전체의 바이트 데이터를 메모리에 로드합니다.

### [Line 20 ~ 30] 멀티모달 요청 콘텐츠(Contents) 구성
```python
20:     contents = [
21:         types.Content(
22:             role="user",
23:             parts=[
24:                 types.Part.from_bytes(
25:                     data=audio_bytes,
26:                     mime_type="audio/wav",
27:                 ),
28:             ],
29:         ),
30:     ]
```
- **Line 20 (`contents = [...]`)**: 모델에 입력으로 보낼 대화 턴 목록입니다.
- **Line 21~22 (`types.Content(role="user", ...)`)**: 사용자 역할(`role="user"`)의 단일 메시지 객체를 선언합니다.
- **Line 23 (`parts=[...]`)**: 메시지를 이루는 구성 파트(텍스트, 이미지, 오디오 등) 목록입니다.
- **Line 24~27 (`types.Part.from_bytes(...)`)**:
  - `data=audio_bytes`: 읽어온 오디오의 원시 바이트 데이터를 전달합니다.
  - `mime_type="audio/wav"`: 입력 데이터가 WAV 규격 오디오임을 지정합니다.

### [Line 31 ~ 36] 음성 인식(STT) 옵션 설정
```python
31:     generate_content_config = types.GenerateContentConfig(
32:         audio_transcription_config=types.AudioTranscriptionConfig(
33:             word_timestamp=True,
34:             diarization=True,
35:         ),
36:     )
```
- **Line 31 (`generate_content_config = types.GenerateContentConfig(...)`)**: 모델 생성 옵션을 설정하는 객체입니다.
- **Line 32 (`audio_transcription_config=types.AudioTranscriptionConfig(...)`)**: STT 전용 상세 설정을 지정합니다.
  - **Line 33 (`word_timestamp=True`)**: 전사 결과에서 단어별 시작/종료 시각(타임스탬프) 정보를 제공하도록 활성화합니다.
  - **Line 34 (`diarization=True`)**: 화자 분리(Diarization)를 활성화하여 여러 화자가 발화할 때 화자(Speaker)를 구분하도록 합니다.

### [Line 38 ~ 44] 스트리밍 요청 및 실시간 출력
```python
38:     for chunk in client.models.generate_content_stream(
39:         model=model,
40:         contents=contents,
41:         config=generate_content_config,
42:     ):
43:         if text := chunk.text:
44:             print(text, end="")
```
- **Line 38~42 (`for chunk in client.models.generate_content_stream(...)`)**:
  - 모델의 전사 결과를 실시간 스트리밍 방식으로 청크 단위로 수신합니다.
- **Line 43~44 (`if text := chunk.text: print(text, end="")`)**:
  - 바다코끼리 연산자(`:=`)로 청크에 텍스트가 있을 경우 이를 꺼내어 줄바꿈 없이 즉시 출력함으로써 실시간 전사 결과를 확인합니다.

### [Line 46 ~ 47] 메인 함수 호출
```python
46: if __name__ == "__main__":
47:     generate()
```
- **Line 46~47**: 스크립트가 직접 실행되었을 때 `generate()` 함수를 실행합니다.

---

## 3. 실행 방법

```powershell
# 1. API 키 환경 변수 등록
$env:GEMINI_API_KEY="본인의_API_키"

# 2. 스크립트 실행
python gemini-35-stt-example.py
```
