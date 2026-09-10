import os
import sys
from pathlib import Path
from dotenv import load_dotenv

current_dir = Path(__file__).resolve().parent
if str(current_dir) not in sys.path:
    sys.path.insert(0, str(current_dir))

# .env 로드
load_dotenv(current_dir / ".env")
load_dotenv(current_dir.parent / ".env")

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional, List, Dict, Any

from services.youtube import extract_video_id, get_video_info, download_audio
from services.transcriber import transcribe_audio_with_gemini
from services.searcher import (
    search_content_timestamp,
    answer_question_with_gemini,
    generate_summary_and_chapters,
    group_transcript_into_contextual_paragraphs
)
from services.csv_storage import find_transcript_in_csv, save_transcript_to_csv

app = FastAPI(title="AI YouTube Searcher", description="AI 유튜브 검색기 - 문맥 기반 타임라인 대본 & 3줄 요약 & 챕터")

BASE_DIR = current_dir
DOWNLOADS_DIR = BASE_DIR / "downloads"
STATIC_DIR = BASE_DIR / "static"
DOWNLOADS_DIR.mkdir(exist_ok=True)
STATIC_DIR.mkdir(exist_ok=True)

# 정적 파일 서빙
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# 요청 모델 정의
class VideoUrlRequest(BaseModel):
    url: str

class SearchRequest(BaseModel):
    query: str
    segments: List[Dict[str, Any]]
    full_text: Optional[str] = ""

class ChatRequest(BaseModel):
    question: str
    transcript: str
    video_title: Optional[str] = ""

@app.get("/", response_class=HTMLResponse)
async def serve_index():
    index_file = STATIC_DIR / "index.html"
    if not index_file.exists():
        raise HTTPException(status_code=404, detail="index.html을 찾을 수 없습니다.")
    return FileResponse(index_file)

@app.post("/api/video-info")
async def fetch_video_info(req: VideoUrlRequest):
    """유튜브 URL로부터 비디오 메타데이터 및 ID 추출 (즉시 플레이어 로딩용)"""
    url = req.url.strip()
    if not url:
        raise HTTPException(status_code=400, detail="유튜브 URL을 입력해 주세요.")
    
    video_id = extract_video_id(url)
    if not video_id:
        raise HTTPException(status_code=400, detail="유효한 유튜브 비디오 ID를 찾을 수 없습니다.")

    # 1. CSV에 이미 메타데이터가 있는지 먼저 확인
    csv_record = find_transcript_in_csv(video_id)
    if csv_record:
        return {
            "success": True,
            "video": {
                "id": csv_record["video_id"],
                "url": csv_record["url"],
                "title": csv_record["title"],
                "uploader": csv_record["uploader"],
                "duration": csv_record["duration"],
                "duration_str": csv_record["duration_str"],
                "thumbnail": f"https://i.ytimg.com/vi/{csv_record['video_id']}/hqdefault.jpg",
                "cached": True
            }
        }

    # 2. CSV에 없으면 yt-dlp로 정보 조회
    try:
        info = get_video_info(url)
        return {"success": True, "video": info}
    except Exception as e:
        return {
            "success": True,
            "video": {
                "id": video_id,
                "url": f"https://www.youtube.com/watch?v={video_id}",
                "title": f"유튜브 동영상 ({video_id})",
                "uploader": "YouTube",
                "duration": 0,
                "duration_str": "00:00",
                "thumbnail": f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"
            }
        }

@app.post("/api/transcribe")
async def process_transcribe(req: VideoUrlRequest):
    """
    1. CSV 파일에서 이전 트랜스크립트 존재 여부 확인
    2. 존재하면 CSV 저장된 대본 및 요약/챕터 즉시 반환 (API 호출 X)
    3. 없으면 오디오 다운로드 + Gemini 3.5 Transcribe STT + 문맥 단락 그룹핑 + 3줄 요약/챕터 생성 후 CSV 저장
    """
    url = req.url.strip()
    if not url:
        raise HTTPException(status_code=400, detail="유튜브 URL을 입력해 주세요.")

    video_id = extract_video_id(url)

    # 1단계: CSV 파일에 이미 저장된 트랜스크립트가 있는지 확인
    csv_data = find_transcript_in_csv(video_id or url)
    if csv_data and csv_data.get("segments"):
        print(f"[API] CSV 저장소에서 트랜스크립트 로드: {video_id}")
        
        # 만약 과거 캐시에 summary_points나 chapters가 없으면 생성해서 CSV 갱신
        summary_points = csv_data.get("summary_points", [])
        chapters = csv_data.get("chapters", [])
        if (not summary_points or not chapters) and csv_data.get("full_text"):
            try:
                ai_sum = generate_summary_and_chapters(
                    transcript=csv_data["full_text"],
                    video_title=csv_data.get("title", "")
                )
                summary_points = ai_sum.get("summary_points", [])
                chapters = ai_sum.get("chapters", [])
                csv_data["summary_points"] = summary_points
                csv_data["chapters"] = chapters
                save_transcript_to_csv(csv_data)
            except Exception as e:
                print(f"기존 캐시 요약 생성 실패: {e}")

        return {
            "success": True,
            "video": {
                "id": csv_data["video_id"],
                "url": csv_data["url"],
                "title": csv_data["title"],
                "uploader": csv_data["uploader"],
                "duration": csv_data["duration"],
                "duration_str": csv_data["duration_str"],
                "thumbnail": f"https://i.ytimg.com/vi/{csv_data['video_id']}/hqdefault.jpg",
            },
            "transcription": {
                "model": csv_data["model"],
                "segments": csv_data["segments"],
                "full_text": csv_data["full_text"],
                "summary_points": summary_points,
                "chapters": chapters,
                "cached": True,
                "source": "csv"
            }
        }

    # 2단계: CSV에 없으면 신규 오디오 다운로드
    try:
        audio_info = download_audio(url, str(DOWNLOADS_DIR))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"오디오 다운로드 실패: {str(e)}")

    # 3단계: Gemini 3.5 Transcribe STT 수행
    try:
        stt_result = transcribe_audio_with_gemini(
            file_path=audio_info["file_path"],
            mime_type=audio_info["mime_type"],
            video_id=audio_info["id"]
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gemini 음성 전사 실패: {str(e)}")

    # 4단계: 문맥과 의미가 연결되는 자연스러운 단락(Paragraph) 단위로 그룹핑
    try:
        contextual_segments = group_transcript_into_contextual_paragraphs(
            raw_transcript=stt_result.get("full_text", ""),
            raw_segments=stt_result.get("segments", [])
        )
        if contextual_segments:
            stt_result["segments"] = contextual_segments
            # full_text도 문맥 단락으로 정리
            stt_result["full_text"] = "\n".join([f"[{s['time_str']}] {s.get('speaker', '화자')}: {s['text']}" for s in contextual_segments])
    except Exception as e:
        print(f"문맥 단락화 처리 실패 ({e}), 기본 세그먼트 유지")

    # 5단계: Gemini 3.8 Flash로 3줄 핵심 요약 및 챕터 목차 생성
    summary_points = []
    chapters = []
    if stt_result.get("full_text"):
        try:
            ai_sum = generate_summary_and_chapters(
                transcript=stt_result["full_text"],
                video_title=audio_info.get("title", "")
            )
            summary_points = ai_sum.get("summary_points", [])
            chapters = ai_sum.get("chapters", [])
        except Exception as e:
            print(f"요약/챕터 생성 실패: {e}")

    stt_result["summary_points"] = summary_points
    stt_result["chapters"] = chapters

    # 6단계: 트랜스크립트 + 요약 + 챕터 결과를 CSV 파일에 영구 저장
    try:
        save_transcript_to_csv({
            "video_id": audio_info["id"],
            "url": audio_info.get("url") or f"https://www.youtube.com/watch?v={audio_info['id']}",
            "title": audio_info.get("title", ""),
            "uploader": audio_info.get("uploader", ""),
            "duration": audio_info.get("duration", 0),
            "duration_str": audio_info.get("duration_str", "00:00"),
            "model": stt_result.get("model", "gemini-3.5-transcribe"),
            "full_text": stt_result.get("full_text", ""),
            "segments": stt_result.get("segments", []),
            "summary_points": summary_points,
            "chapters": chapters
        })
    except Exception as e:
        print(f"CSV 저장 중 오류: {e}")

    return {
        "success": True,
        "video": audio_info,
        "transcription": stt_result
    }

@app.post("/api/search")
async def search_content(req: SearchRequest):
    """영상 내용 검색 -> 타임스탬프 위치 탐색"""
    if not req.query.strip():
        raise HTTPException(status_code=400, detail="검색어를 입력해 주세요.")
    try:
        result = search_content_timestamp(
            query=req.query,
            segments=req.segments,
            full_text=req.full_text or ""
        )
        return {"success": True, "data": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"검색 처리 중 오류: {str(e)}")

@app.post("/api/chat")
async def chat_with_video(req: ChatRequest):
    """Gemini 3.8 Flash 모델을 사용한 영상 내용 기반 질문 답변"""
    if not req.question.strip():
        raise HTTPException(status_code=400, detail="질문 내용을 입력해 주세요.")
    try:
        result = answer_question_with_gemini(
            question=req.question,
            transcript=req.transcript,
            video_title=req.video_title or ""
        )
        return {"success": True, "data": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"질변 답변 생성 중 오류: {str(e)}")

@app.get("/api/audio/{file_name}")
async def get_audio_file(file_name: str):
    file_path = DOWNLOADS_DIR / file_name
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="오디오 파일을 찾을 수 없습니다.")
    return FileResponse(file_path)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8001, reload=True)
