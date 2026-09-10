import os
import json
import time
import re
from pathlib import Path
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()
load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")

def get_client() -> genai.Client:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY 환경변수가 설정되지 않았습니다.")
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

def split_words_into_sentence_segments(words: list, default_speaker: str = "화자") -> list:
    """
    단어 목록(각각 word, start_offset)을 순회하며
    마침표, 물음표, 한국어 종결어미 등을 기준으로 적절한 길이(1~2문장, 5~15단어) 단위로 세분화 분할
    """
    if not words:
        return []

    segments = []
    current_words = []
    seg_start_offset = None

    def is_sentence_end(text: str) -> bool:
        t = text.strip()
        if not t:
            return False
        if t.endswith((".", "?", "!", "…")):
            return True
        endings = (
            "습니다", "합니다", "입니다", "됩니다", "있습니다", "없습니다", 
            "했습니다", "답니다", "는데요", "지요", "네요", "하죠", 
            "왔다", "됐다", "된다", "했다", "한다", "이다", "아닙니다"
        )
        for ed in endings:
            if t.endswith(ed):
                return True
        return False

    for w in words:
        w_text = getattr(w, "word", getattr(w, "text", "")).strip()
        w_offset = getattr(w, "start_offset", 0.0)

        if not w_text:
            continue

        if seg_start_offset is None:
            seg_start_offset = w_offset

        current_words.append(w_text)

        # 1. 마침표나 종결 어미로 끝나고 최소 5단어 이상 모였을 때
        # 2. 또는 문장이 16단어 이상 길어졌을 때 자연스럽게 분할
        if (is_sentence_end(w_text) and len(current_words) >= 5) or len(current_words) >= 16:
            sec, time_str = format_timestamp(seg_start_offset)
            combined_text = " ".join(current_words)
            segments.append({
                "start_seconds": round(sec, 1),
                "time_str": time_str,
                "speaker": default_speaker,
                "text": combined_text
            })
            current_words = []
            seg_start_offset = None

    # 남아있는 잔여 단어 처리
    if current_words:
        sec, time_str = format_timestamp(seg_start_offset)
        combined_text = " ".join(current_words)
        segments.append({
            "start_seconds": round(sec, 1),
            "time_str": time_str,
            "speaker": default_speaker,
            "text": combined_text
        })

    return segments

def transcribe_audio_with_gemini(file_path: str, mime_type: str = "audio/mp4", video_id: str = "") -> dict:
    """
    gemini-3.5-transcribe 모델을 사용하여 오디오 파일에서
    세분화된 타임스탬프와 문장별 트랜스크립트를 정밀 추출
    """
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
                            if words:
                                # ✨ 단어별 타임스탬프를 기반으로 문장 단위 세분화 분할!
                                sub_segs = split_words_into_sentence_segments(words, default_speaker=speaker)
                                for s in sub_segs:
                                    segments.append(s)
                                    full_text_lines.append(f"[{s['time_str']}] {s['speaker']}: {s['text']}")
                            else:
                                raw_offset = getattr(at, "start_offset", 0.0)
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
                "대화가 시작되는 시간대별(예: [00:15])로 5~15초 단위의 세부 타임스탬프와 대사를 작성해주세요."
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

        return {
            "model": target_model,
            "segments": segments,
            "full_text": "\n".join(full_text_lines),
            "cached": False
        }

    finally:
        if uploaded_file:
            try:
                client.files.delete(name=uploaded_file.name)
            except Exception:
                pass
