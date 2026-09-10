import os
import time
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

def get_client() -> genai.Client:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY 환경 변수가 설정되지 않았습니다. .env 파일을 확인해 주세요.")
    return genai.Client(api_key=api_key)

def format_timestamp(raw_offset) -> str:
    """초 또는 '4.08s' 형태의 오프셋을 [MM:SS] 형식으로 변환"""
    if not raw_offset:
        return "00:00"
    try:
        s_str = str(raw_offset).rstrip("s")
        sec = float(s_str)
        m = int(sec // 60)
        s = int(sec % 60)
        return f"{m:02d}:{s:02d}"
    except Exception:
        return str(raw_offset)

def parse_transcribe_response(response) -> str:
    """gemini-3.5-transcribe 모델의 구조화된 오디오 전사 응답을 포맷팅"""
    if not response or not response.candidates:
        return "트랜스크립트를 생성할 수 없습니다."

    candidate = response.candidates[0]
    if not candidate.content or not candidate.content.parts:
        if response.text:
            return response.text
        return "음성을 인식하지 못했거나 오디오에 음성이 감지되지 않았습니다."

    formatted_lines = []
    plain_texts = []

    for part in candidate.content.parts:
        at = getattr(part, "audio_transcription", None)
        if at:
            speaker = getattr(at, "speaker_label", "화자")
            if speaker and speaker.startswith("spk:"):
                try:
                    num = int(speaker.split(":")[1]) + 1
                    speaker = f"화자 {num}"
                except Exception:
                    pass
            
            words = getattr(at, "words", [])
            start_time = "00:00"
            if words and hasattr(words[0], "start_offset"):
                start_time = format_timestamp(words[0].start_offset)
            
            seg_text = getattr(at, "text", "")
            if seg_text:
                formatted_lines.append(f"**[{start_time}]** **{speaker}:** {seg_text}")
                plain_texts.append(seg_text)
        elif getattr(part, "text", None):
            plain_texts.append(part.text)

    if formatted_lines:
        return "\n\n".join(formatted_lines)
    elif plain_texts:
        return "\n\n".join(plain_texts)
    elif response.text:
        return response.text

    return "트랜스크립트를 생성할 수 없습니다."

def transcribe_audio_file(
    file_path: str,
    mime_type: str = "audio/mp4",
    model: str = "gemini-3.6-flash",
    prompt_instruction: str = None
) -> dict:
    """Gemini API를 사용하여 오디오 파일의 트랜스크립트(대본)를 생성합니다."""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"오디오 파일을 찾을 수 없습니다: {file_path}")

    client = get_client()
    file_size = os.path.getsize(file_path)
    is_transcribe_model = "transcribe" in model.lower()

    uploaded_file = None
    try:
        # 오디오 파트 준비
        if file_size <= 20 * 1024 * 1024:
            with open(file_path, "rb") as f:
                audio_bytes = f.read()
            audio_part = types.Part.from_bytes(
                data=audio_bytes,
                mime_type=mime_type,
            )
        else:
            uploaded_file = client.files.upload(file=file_path)
            while uploaded_file.state.name == "PROCESSING":
                time.sleep(2)
                uploaded_file = client.files.get(name=uploaded_file.name)
            audio_part = uploaded_file

        # 모델별 분기 처리
        if is_transcribe_model:
            # gemini-3.5-transcribe는 음성 전용 특화 모델:
            # 텍스트 프롬프트를 넣으면 동작하지 않으므로 오디오 파트만 단독 전달하고 전사용 config 적용
            contents = [
                types.Content(
                    role="user",
                    parts=[audio_part],
                )
            ]
            config = types.GenerateContentConfig(
                audio_transcription_config=types.AudioTranscriptionConfig(
                    word_timestamp=True,
                    diarization=True,
                )
            )
            response = client.models.generate_content(
                model=model,
                contents=contents,
                config=config,
            )
            transcript_text = parse_transcribe_response(response)

        else:
            # gemini-3.6-flash 등의 일반 멀티모달 LLM:
            # 텍스트 프롬프트와 오디오 파트를 함께 전달하여 요약과 타임스탬프 대본 생성
            if not prompt_instruction:
                prompt_instruction = (
                    "아래 오디오를 듣고 한국어 또는 원어 발화 내용을 정확하게 전사(Transcription)해 주세요.\n\n"
                    "요구사항:\n"
                    "1. 대화가 시작되는 시간대별(예: [00:15] 또는 [01:20])로 타임스탬프를 적어주세요.\n"
                    "2. 여러 화자가 있는 경우 '화자 1:', '화자 2:' 등으로 구분해 주세요.\n"
                    "3. 맞춤법과 띄어쓰기를 정확하게 유지해 주세요.\n"
                    "4. 맨 앞에는 전체 내용에 대한 3줄 핵심 요약을 먼저 제공하고, 그 아래에 전체 타임스탬프 대본을 출력해 주세요."
                )

            contents = [
                types.Content(
                    role="user",
                    parts=[
                        types.Part.from_text(text=prompt_instruction),
                        audio_part,
                    ],
                )
            ]
            response = client.models.generate_content(
                model=model,
                contents=contents,
            )
            transcript_text = response.text or "트랜스크립트를 생성할 수 없습니다."

        return {
            "success": True,
            "transcript": transcript_text,
            "model": model,
        }

    finally:
        if uploaded_file:
            try:
                client.files.delete(name=uploaded_file.name)
            except Exception:
                pass
