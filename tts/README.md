# Gemini 3.1 Flash TTS (Text-to-Speech) 코드 라인별 해설

본 문서는 `gemini-31-tts-example.py` 파일의 소스 코드를 라인별(Line-by-Line)로 상세히 설명합니다.

---

## 1. 전체 소스 코드

```python
# To run this code you need to install the following dependencies:
# pip install google-genai

import mimetypes
import os
import re
import struct
from google import genai
from google.genai import types


def save_binary_file(file_name, data):
    f = open(file_name, "wb")
    f.write(data)
    f.close()
    print(f"File saved to to: {file_name}")


def generate():
    client = genai.Client(
        api_key=os.environ.get("GEMINI_API_KEY"),
    )

    model = "gemini-3.1-flash-tts-preview"
    contents = [
        types.Content(
            role="user",
            parts=[
                types.Part.from_text(text="""Read the following transcript based on the audio profile.

# Audio Profile
warm

## Scene:
A professional TV news studio breaking a shocking tech industry announcement.

## Sample Context:
The news anchor is delivering an urgent breaking news report with a fast-paced, enthusiastic, and astonished tone about Google's disruptive pricing.

## Transcript:
[urgent] 속보입니다! 구글이 차세대 인공지능 모델, '제미나이 4.0 Pro'를 전격 공개했습니다. [excited] 그런데 성능보다 더 전 세계를 충격에 빠뜨린 건 바로 가격입니다. [amazed] 기존 모델 대비 무려 90% 이상 파격적으로 인하된, 그야말로 '역대급 헐값' 수준으로 책정되었다는 소식인데요! [confident] 업계에서는 AI 시장의 판도를 완전히 뒤흔들 게임 체인저가 등장했다며 술렁이고 있습니다."""),
            ],
        ),
    ]
    generate_content_config = types.GenerateContentConfig(
        temperature=1,
        response_modalities=[
            "audio",
        ],
        speech_config=types.SpeechConfig(
            voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(
                    voice_name="Kore"
                )
            )
        ),
    )

    audio_chunks = bytearray()
    mime_type = None

    print("음성 생성 중...")
    for chunk in client.models.generate_content_stream(
        model=model,
        contents=contents,
        config=generate_content_config,
    ):
        if chunk.parts is None:
            continue
        if chunk.parts[0].inline_data and chunk.parts[0].inline_data.data:
            inline_data = chunk.parts[0].inline_data
            mime_type = inline_data.mime_type
            audio_chunks.extend(inline_data.data)
        else:
            if text := chunk.text:
                print(text)

    if audio_chunks and mime_type:
        output_file = "output.wav"
        wav_data = convert_to_wav(bytes(audio_chunks), mime_type)
        save_binary_file(output_file, wav_data)
        print(f"완성된 음성 파일이 저장되었습니다: {output_file}")

def convert_to_wav(audio_data: bytes, mime_type: str) -> bytes:
    """Generates a WAV file header for the given audio data and parameters.

    Args:
        audio_data: The raw audio data as a bytes object.
        mime_type: Mime type of the audio data.

    Returns:
        A bytes object representing the WAV file header.
    """
    parameters = parse_audio_mime_type(mime_type)
    bits_per_sample = parameters["bits_per_sample"]
    sample_rate = parameters["rate"]
    num_channels = 1
    data_size = len(audio_data)
    bytes_per_sample = bits_per_sample // 8
    block_align = num_channels * bytes_per_sample
    byte_rate = sample_rate * block_align
    chunk_size = 36 + data_size  # 36 bytes for header fields before data chunk size

    # http://soundfile.sapp.org/doc/WaveFormat/

    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF",          # ChunkID
        chunk_size,       # ChunkSize (total file size - 8 bytes)
        b"WAVE",          # Format
        b"fmt ",          # Subchunk1ID
        16,               # Subchunk1Size (16 for PCM)
        1,                # AudioFormat (1 for PCM)
        num_channels,     # NumChannels
        sample_rate,      # SampleRate
        byte_rate,        # ByteRate
        block_align,      # BlockAlign
        bits_per_sample,  # BitsPerSample
        b"data",          # Subchunk2ID
        data_size         # Subchunk2Size (size of audio data)
    )
    return header + audio_data

def parse_audio_mime_type(mime_type: str) -> dict[str, int | None]:
    """Parses bits per sample and rate from an audio MIME type string.

    Assumes bits per sample is encoded like "L16" and rate as "rate=xxxxx".

    Args:
        mime_type: The audio MIME type string (e.g., "audio/L16;rate=24000").

    Returns:
        A dictionary with "bits_per_sample" and "rate" keys. Values will be
        integers if found, otherwise None.
    """
    bits_per_sample = 16
    rate = 24000

    # Extract rate from parameters
    parts = mime_type.split(";")
    for param in parts: # Skip the main type part
        param = param.strip()
        if param.lower().startswith("rate="):
            try:
                rate_str = param.split("=", 1)[1]
                rate = int(rate_str)
            except (ValueError, IndexError):
                # Handle cases like "rate=" with no value or non-integer value
                pass # Keep rate as default
            except (ValueError, IndexError):
                pass
        elif param.startswith("audio/L"):
            try:
                bits_per_sample = int(param.split("L", 1)[1])
            except (ValueError, IndexError):
                pass # Keep bits_per_sample as default if conversion fails

    return {"bits_per_sample": bits_per_sample, "rate": rate}


if __name__ == "__main__":
    generate()
```

---

## 2. 라인별 상세 설명

### [Line 1 ~ 2] 의존성 패키지 안내
```python
1: # To run this code you need to install the following dependencies:
2: # pip install google-genai
```
- 구글의 공식 GenAI SDK(`google-genai`) 설치 안내 주석입니다.

### [Line 4 ~ 9] 모듈 임포트
```python
4: import mimetypes
5: import os
6: import re
7: import struct
8: from google import genai
9: from google.genai import types
```
- **Line 4 (`import mimetypes`)**: 파일 확장자와 MIME 타입을 매핑할 때 사용되는 기본 모듈입니다.
- **Line 5 (`import os`)**: 환경 변수(`GEMINI_API_KEY`)를 읽어오기 위해 사용됩니다.
- **Line 6 (`import re`)**: 정규 표현식 모듈입니다.
- **Line 7 (`import struct`)**: 파이썬 값들을 C 언어 바이너리 구조체(바이트 열)로 패킹/언패킹하는 모듈로, WAV 헤더를 직접 빌드할 때 사용됩니다.
- **Line 8~9 (`from google import genai`, `from google.genai import types`)**: 최신 Gemini API SDK 클라이언트 및 데이터 타입 클래스들을 임포트합니다.

### [Line 12 ~ 17] 바이너리 파일 저장 함수
```python
12: def save_binary_file(file_name, data):
13:     f = open(file_name, "wb")
14:     f.write(data)
15:     f.close()
16:     print(f"File saved to to: {file_name}")
```
- **Line 12~16**: 생성된 오디오 데이터(바이트 열)를 지정한 파일 이름(`file_name`)으로 바이너리 쓰기(`"wb"`) 모드로 저장하고 콘솔에 알림을 출력합니다.

### [Line 19 ~ 23] 메인 함수 및 클라이언트 초기화
```python
19: def generate():
20:     client = genai.Client(
21:         api_key=os.environ.get("GEMINI_API_KEY"),
22:     )
```
- **Line 19 (`def generate():`)**: TTS 음성 생성 전체 파이프라인을 실행하는 함수입니다.
- **Line 20~22 (`client = genai.Client(...)`)**: 환경 변수에 등록된 `GEMINI_API_KEY`로 클라이언트를 초기화합니다.

### [Line 24 ~ 44] 모델 지정 및 프롬프트/대본 작성
```python
24:     model = "gemini-3.1-flash-tts-preview"
25:     contents = [
26:         types.Content(
27:             role="user",
28:             parts=[
29:                 types.Part.from_text(text="""Read the following transcript based on the audio profile.
...
41: [urgent] 속보입니다! 구글이 차세대 인공지능 모델... [excited] ... [amazed] ... [confident] ..."""),
42:             ],
43:         ),
44:     ]
```
- **Line 24 (`model = "gemini-3.1-flash-tts-preview"`)**: 음성 생성을 지원하는 Gemini TTS 프리뷰 모델을 지정합니다.
- **Line 25~44 (`contents = [...]`)**:
  - 모델에게 읽어줄 대본(Transcript)뿐만 아니라 **음성 프로필(Audio Profile)**, **상황(Scene)**, **문맥(Sample Context)**을 프롬프트로 지정합니다.
  - 대본 본문에 `[urgent]`, `[excited]`, `[amazed]`, `[confident]` 등 감정 및 톤 지시 태그를 삽입하여 생생하고 감정이 담긴 음성을 유도합니다.

### [Line 45 ~ 58] 응답 모달리티 및 음성 설정
```python
45:     generate_content_config = types.GenerateContentConfig(
46:         temperature=1,
47:         response_modalities=[
48:             "audio",
49:         ],
50:         speech_config=types.SpeechConfig(
51:             voice_config=types.VoiceConfig(
52:                 prebuilt_voice_config=types.PrebuiltVoiceConfig(
53:                     voice_name="Kore"
54:                 )
55:             )
56:         ),
57:     )
```
- **Line 46 (`temperature=1`)**: 출력 다양성과 감정 표현의 풍부함을 조절하는 파라미터입니다.
- **Line 47~49 (`response_modalities=["audio"]`)**: 모델의 응답 결과로 텍스트 대신 **오디오(음성 바이너리)**를 반환하도록 지정합니다.
- **Line 50~56 (`speech_config=...`)**:
  - 생성할 목소리의 종류를 사전 제공 음성(`PrebuiltVoiceConfig`) 중 `"Kore"`로 지정합니다.

### [Line 59 ~ 61] 스트리밍 수신 변수 준비
```python
59:     audio_chunks = bytearray()
60:     mime_type = None
```
- **Line 59 (`audio_chunks = bytearray()`)**: 스트리밍으로 전달되는 오디오 바이트 조각들을 누적 저장할 가변 바이트 배열입니다.
- **Line 60 (`mime_type = None`)**: 모델이 반환하는 오디오의 MIME 타입 정보를 저장할 변수입니다.

### [Line 62 ~ 77] 스트리밍 생성 루프 및 바이너리 수집
```python
62:     print("음성 생성 중...")
63:     for chunk in client.models.generate_content_stream(
64:         model=model,
65:         contents=contents,
66:         config=generate_content_config,
67:     ):
68:         if chunk.parts is None:
69:             continue
70:         if chunk.parts[0].inline_data and chunk.parts[0].inline_data.data:
71:             inline_data = chunk.parts[0].inline_data
72:             mime_type = inline_data.mime_type
73:             audio_chunks.extend(inline_data.data)
74:         else:
75:             if text := chunk.text:
76:                 print(text)
```
- **Line 63~67**: 스트리밍 API를 호출하여 청크를 차례로 받아옵니다.
- **Line 68~69**: 유효하지 않은 청크는 건너뜁니다.
- **Line 70~73**:
  - 청크에 `inline_data`가 포함되어 있으면 해당 MIME 타입(예: `audio/L16;rate=24000`)을 기록하고,
  - 바이트 배열 `audio_chunks`에 원시 오디오 데이터를 추가(`extend`)합니다.
- **Line 74~76**: 만약 텍스트 형태의 응답이 포함되어 있다면 콘솔에 출력합니다.

### [Line 78 ~ 83] WAV 파일 변환 및 저장
```python
78:     if audio_chunks and mime_type:
79:         output_file = "output.wav"
80:         wav_data = convert_to_wav(bytes(audio_chunks), mime_type)
81:         save_binary_file(output_file, wav_data)
82:         print(f"완성된 음성 파일이 저장되었습니다: {output_file}")
```
- **Line 78~83**:
  - 수집된 오디오 조각이 존재하면, `convert_to_wav` 함수를 호출해 PCM 데이터를 재생 가능한 표준 WAV 포맷으로 변환합니다.
  - 이를 `output.wav` 파일로 저장하고 완료 메시지를 출력합니다.

### [Line 84 ~ 122] PCM 데이터를 WAV 파일로 변환하는 함수
```python
84: def convert_to_wav(audio_data: bytes, mime_type: str) -> bytes:
...
106:     header = struct.pack(
107:         "<4sI4s4sIHHIIHH4sI",
...
122:     return header + audio_data
```
- **Line 84~103**:
  - MIME 타입에서 샘플 레이트(기본 24,000Hz), 비트 수(기본 16비트), 채널 수(모노: 1)를 계산하고, WAV 규격에 맞는 청크 크기와 바이트 레이트를 계산합니다.
- **Line 106~121 (`struct.pack("<4sI4s4sIHHIIHH4sI", ...)`)**:
  - 파이썬 `struct` 모듈을 이용해 44바이트의 표준 RIFF/WAVE 헤더 바이너리를 리틀 엔디언(`"<"`) 형식으로 패킹합니다:
    - `RIFF`: RIFF 컨테이너 식별자
    - `chunk_size`: 전체 파일 크기 - 8 바이트
    - `WAVE`: 오디오 포맷
    - `fmt `: 서브 청크 1 식별자
    - `16, 1`: PCM 포맷 지정
    - `num_channels`, `sample_rate`, `byte_rate`, `block_align`, `bits_per_sample`
    - `data`, `data_size`: 실제 PCM 데이터 청크 헤더
- **Line 122 (`return header + audio_data`)**:
  - 44바이트 WAV 헤더 뒤에 원시 오디오 데이터를 이어 붙여 완전한 WAV 바이너리를 반환합니다.

### [Line 124 ~ 156] MIME 타입 파싱 유틸리티 함수
```python
124: def parse_audio_mime_type(mime_type: str) -> dict[str, int | None]:
...
156:     return {"bits_per_sample": bits_per_sample, "rate": rate}
```
- **Line 124~156**:
  - 모델이 반환한 `audio/L16;rate=24000` 같은 MIME 문자열을 세미콜론(`;`)으로 분리하여 샘플 레이트(`rate=24000`)와 비트 깊이(`L16` -> 16비트)를 추출합니다.
  - 파싱 실패 시 기본값(16비트, 24,000Hz)을 반환하여 안정성을 보장합니다.

### [Line 159 ~ 160] 실행 진입점
```python
159: if __name__ == "__main__":
160:     generate()
```
- **Line 159~160**: 스크립트 실행 시 `generate()`를 호출하여 음성 합성을 진행합니다.

---

## 3. 실행 방법

```powershell
# 1. API 키 환경 변수 등록
$env:GEMINI_API_KEY="본인의_API_키"

# 2. 스크립트 실행
python gemini-31-tts-example.py
```
실행이 완료되면 디렉토리에 `output.wav` 파일이 생성됩니다.
