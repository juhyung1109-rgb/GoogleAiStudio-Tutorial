import os
import csv
import json
import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List

# CSV 저장 경로 (ai_youtube_searcher 루트 기준)
BASE_DIR = Path(__file__).resolve().parent.parent
CSV_FILE_PATH = BASE_DIR / "transcripts.csv"

CSV_HEADERS = [
    "video_id",
    "url",
    "title",
    "uploader",
    "duration",
    "duration_str",
    "model",
    "full_text",
    "segments_json",
    "created_at"
]

def init_csv_file():
    """CSV 파일이 없으면 헤더와 함께 utf-8-sig 인코딩으로 생성"""
    if not CSV_FILE_PATH.exists():
        with open(CSV_FILE_PATH, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerow(CSV_HEADERS)

def find_transcript_in_csv(url_or_id: str) -> Optional[Dict[str, Any]]:
    """
    CSV 파일에서 url 또는 video_id가 일치하는 레코드를 검색하여 반환
    없으면 None 반환
    """
    if not CSV_FILE_PATH.exists():
        return None

    target = url_or_id.strip().lower()

    try:
        with open(CSV_FILE_PATH, "r", newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                v_id = (row.get("video_id") or "").strip().lower()
                v_url = (row.get("url") or "").strip().lower()

                # url 또는 video_id 일치 여부 확인
                if (v_id and (v_id in target or target == v_id)) or (v_url and (v_url == target or v_id in target)):
                    segments = []
                    raw_segments = row.get("segments_json", "")
                    if raw_segments:
                        try:
                            segments = json.loads(raw_segments)
                        except Exception:
                            segments = []

                    return {
                        "video_id": row.get("video_id", ""),
                        "url": row.get("url", ""),
                        "title": row.get("title", ""),
                        "uploader": row.get("uploader", ""),
                        "duration": int(row.get("duration") or 0),
                        "duration_str": row.get("duration_str", "00:00"),
                        "model": row.get("model", "gemini-3.5-transcribe"),
                        "full_text": row.get("full_text", ""),
                        "segments": segments,
                        "created_at": row.get("created_at", ""),
                        "cached": True,
                        "source": "csv"
                    }
    except Exception as e:
        print(f"[CSV Storage] Search Error: {e}")

    return None

def save_transcript_to_csv(record: Dict[str, Any]) -> bool:
    """
    트랜스크립트 데이터를 CSV 파일에 저장 (이미 동일 video_id가 있으면 갱신, 없으면 추가)
    """
    init_csv_file()
    
    video_id = record.get("video_id", "")
    url = record.get("url", f"https://www.youtube.com/watch?v={video_id}")
    title = record.get("title", "")
    uploader = record.get("uploader", "")
    duration = record.get("duration", 0)
    duration_str = record.get("duration_str", "00:00")
    model = record.get("model", "gemini-3.5-transcribe")
    full_text = record.get("full_text", "")
    segments = record.get("segments", [])
    segments_json = json.dumps(segments, ensure_ascii=False)
    created_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    new_row = {
        "video_id": video_id,
        "url": url,
        "title": title,
        "uploader": uploader,
        "duration": str(duration),
        "duration_str": duration_str,
        "model": model,
        "full_text": full_text,
        "segments_json": segments_json,
        "created_at": created_at
    }

    # 기존 데이터 읽기
    rows = []
    updated = False
    try:
        with open(CSV_FILE_PATH, "r", newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get("video_id") == video_id:
                    # 덮어쓰기(갱신)
                    rows.append(new_row)
                    updated = True
                else:
                    rows.append(row)
    except Exception as e:
        print(f"[CSV Storage] Read Error: {e}")

    if not updated:
        rows.append(new_row)

    # 다시 쓰기
    try:
        with open(CSV_FILE_PATH, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=CSV_HEADERS)
            writer.writeheader()
            writer.writerows(rows)
        print(f"[CSV Storage] Saved: {video_id} ({title})")
        return True
    except Exception as e:
        print(f"[CSV Storage] Save Error: {e}")
        return False
