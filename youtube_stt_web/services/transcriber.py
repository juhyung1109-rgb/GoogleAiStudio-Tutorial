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

    if not prompt_instruction:
        prompt_instruction = (
            "아래 오디오를 듣고 한국어 또는 원어 발화 내용을 정확하게 전사(Transcription)해 주세요.\n\n"
            "요구사항:\n"
            "1. 대화가 시작되는 시간대별(예: [00:15] 또는 [01:20])로 타임스탬프를 적어주세요.\n"
            "2. 여러 화자가 있는 경우 '화자 1:', '화자 2:' 등으로 구분해 주세요.\n"
            "3. 맞춤법과 띄어쓰기를 정확하게 유지해 주세요.\n"
            "4. 맨 앞에는 전체 내용에 대한 3줄 핵심 요약을 먼저 제공하고, 그 아래에 전체 타임스탬프 대본을 출력해 주세요."
        )

    uploaded_file = None
    try:
        if file_size <= 20 * 1024 * 1024:
            with open(file_path, "rb") as f:
                audio_bytes = f.read()
            audio_part = types.Part.from_bytes(
                data=audio_bytes,
                mime_type=mime_type,
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
        else:
            uploaded_file = client.files.upload(file=file_path)
            while uploaded_file.state.name == "PROCESSING":
                time.sleep(2)
                uploaded_file = client.files.get(name=uploaded_file.name)
            
            contents = [
                types.Content(
                    role="user",
                    parts=[
                        types.Part.from_text(text=prompt_instruction),
                        uploaded_file,
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
