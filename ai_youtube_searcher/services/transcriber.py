import os
import json
import time
from pathlib import Path
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()
load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")

def get_client() -> genai.Client:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY 환경변수가 설정되지 않았습니다. .env 파일을 확인해주세요.")
    return genai.Client(api_key=api_key)

def format_timestamp(raw_offset) -> tuple[float, str]:
    """초 또는 '4.08s' 형태의 오프셋을 (초_float, MM:SS) 튜플로 변환"""
    if not raw_offset:
        return 0.0, "00:00"
    try:
        s_str = str(raw_offset).rstrip("s")
        sec = float(s_str)
        m = int(sec // 60)
        s = int(sec % 60)
        return sec, f"{m:02d}:{s:02d}"
    except Exception:
        return 0.0, "00:00"

def transcribe_audio_with_gemini(file_path: str, mime_type: str = "audio/mp4", video_id: str = "") -> dict:
    """
    gemini-3.5-transcribe 모델을 사용하여 오디오 파일에서 타임스탬프와 트랜스크립트를 추출
    결과는 JSON 캐시로 저장하여 빠른 재사용 가능
    """
    cache_path = None
    if video_id:
        cache_path = Path(file_path).parent / f"{video_id}_transcript.json"
        if cache_path.exists():
            try:
                with open(cache_path, "r", encoding="utf-8") as f:
                    cached_data = json.load(f)
                    cached_data["cached"] = True
                    return cached_data
            except Exception:
                pass

    if not os.path.exists(file_path):
        raise FileNotFoundError(f"오디오 파일을 찾을 수 없습니다: {file_path}")

    client = get_client()
    file_size = os.path.getsize(file_path)
    uploaded_file = None

    try:
        # 오디오 파트 준비
        if file_size <= 20 * 1024 * 1024:
            with open(file_path, "rb") as f:
                audio_bytes = f.read()
            audio_part = types.Part.from_bytes(
                data=audio_bytes,
                mime_type=mime_type or "audio/mp4"
            )
        else:
            uploaded_file = client.files.upload(file=file_path)
            while uploaded_file.state.name == "PROCESSING":
                time.sleep(2)
                uploaded_file = client.files.get(name=uploaded_file.name)
            audio_part = uploaded_file

        target_model = "gemini-3.5-transcribe"
        segments = []
        full_text_lines = []

        try:
            # gemini-3.5-transcribe 전용 호출
            contents = [
                types.Content(
                    role="user",
                    parts=[audio_part]
                )
            ]
            config = types.GenerateContentConfig(
                audio_transcription_config=types.AudioTranscriptionConfig(
                    word_timestamp=True,
                    diarization=True
                )
            )

            response = client.models.generate_content(
                model=target_model,
                contents=contents,
                config=config
            )

            if response and response.candidates:
                candidate = response.candidates[0]
                if candidate.content and candidate.content.parts:
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
                            raw_offset = 0.0
                            if words and hasattr(words[0], "start_offset"):
                                raw_offset = words[0].start_offset
                            
                            sec, time_str = format_timestamp(raw_offset)
                            seg_text = getattr(at, "text", "").strip()
                            
                            if seg_text:
                                segments.append({
                                    "start_seconds": round(sec, 1),
                                    "time_str": time_str,
                                    "speaker": speaker,
                                    "text": seg_text
                                })
                                full_text_lines.append(f"[{time_str}] {speaker}: {seg_text}")

            if not segments and response.text:
                plain = response.text.strip()
                segments.append({
                    "start_seconds": 0.0,
                    "time_str": "00:00",
                    "speaker": "전체",
                    "text": plain
                })
                full_text_lines.append(f"[00:00] {plain}")

        except Exception as err:
            print(f"gemini-3.5-transcribe 실패 ({err}), gemini-2.5-flash 모델로 시도...")
            target_model = "gemini-2.5-flash"
            fallback_prompt = (
                "아래 오디오를 듣고 한국어 발화 내용을 정확하게 전사해주세요.\n"
                "대화가 시작되는 시간대별(예: [00:15])로 타임스탬프와 대사를 작성해주세요."
            )
            contents = [
                types.Content(
                    role="user",
                    parts=[
                        types.Part.from_text(text=fallback_prompt),
                        audio_part
                    ]
                )
            ]
            response = client.models.generate_content(
                model=target_model,
                contents=contents
            )
            raw_text = response.text or ""
            # 줄단위 파싱
            import re
            for line in raw_text.split("\n"):
                line = line.strip()
                if not line:
                    continue
                match = re.search(r"\[(\d{1,2}:\d{2})\]\s*(?:(.*?):)?\s*(.*)", line)
                if match:
                    t_str = match.group(1)
                    spk = match.group(2) or "화자"
                    txt = match.group(3) or line
                    m, s = t_str.split(":")
                    sec = int(m) * 60 + int(s)
                    segments.append({
                        "start_seconds": sec,
                        "time_str": t_str,
                        "speaker": spk,
                        "text": txt
                    })
                    full_text_lines.append(f"[{t_str}] {spk}: {txt}")
                else:
                    full_text_lines.append(line)

            if not segments:
                segments.append({
                    "start_seconds": 0.0,
                    "time_str": "00:00",
                    "speaker": "전체",
                    "text": raw_text
                })

        result = {
            "model": target_model,
            "segments": segments,
            "full_text": "\n".join(full_text_lines),
            "cached": False
        }

        # 캐시 저장
        if cache_path:
            try:
                with open(cache_path, "w", encoding="utf-8") as f:
                    json.dump(result, f, ensure_ascii=False, indent=2)
            except Exception as e:
                print(f"캐시 저장 오류: {e}")

        return result

    finally:
        if uploaded_file:
            try:
                client.files.delete(name=uploaded_file.name)
            except Exception:
                pass
