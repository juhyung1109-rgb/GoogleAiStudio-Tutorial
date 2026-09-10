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
from services.searcher import search_content_timestamp, answer_question_with_gemini

app = FastAPI(title="AI YouTube Searcher", description="AI 유튜브 검색기 - 타임스탬프 기반 탐색 & Gemini 3.8 Flash Q&A")

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

    try:
        info = get_video_info(url)
        return {"success": True, "video": info}
    except Exception as e:
        # 메타데이터 추출 실패 시에도 최소 비디오 ID로 시청 가능하게 반환
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
    """오디오 다운로드 및 Gemini 3.5 Transcribe STT 수행"""
    url = req.url.strip()
    if not url:
        raise HTTPException(status_code=400, detail="유튜브 URL을 입력해 주세요.")

    # 1. 오디오 다운로드
    try:
        audio_info = download_audio(url, str(DOWNLOADS_DIR))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"오디오 다운로드 실패: {str(e)}")

    # 2. Gemini STT 전사 및 타임스탬프 추출
    try:
        result = transcribe_audio_with_gemini(
            file_path=audio_info["file_path"],
            mime_type=audio_info["mime_type"],
            video_id=audio_info["id"]
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gemini 음성 전사 실패: {str(e)}")

    return {
        "success": True,
        "video": audio_info,
        "transcription": result
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
