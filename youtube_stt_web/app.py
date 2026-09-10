import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# 현재 디렉토리 및 상위 디렉토리를 모듈 검색 경로에 등록
current_dir = Path(__file__).resolve().parent
if str(current_dir) not in sys.path:
    sys.path.insert(0, str(current_dir))

# .env 로드 (루트 및 현재 폴더)
load_dotenv(current_dir / ".env")
load_dotenv(current_dir.parent / ".env")

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from services.youtube import get_video_info, download_audio
from services.transcriber import transcribe_audio_file

app = FastAPI(title="YouTube Audio Downloader & Gemini STT")

BASE_DIR = current_dir
DOWNLOADS_DIR = BASE_DIR / "downloads"
STATIC_DIR = BASE_DIR / "static"
DOWNLOADS_DIR.mkdir(exist_ok=True)
STATIC_DIR.mkdir(exist_ok=True)

# 정적 파일 마운트
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

class ProcessRequest(BaseModel):
    url: str
    model: str = "gemini-3.6-flash"
    prompt: str = ""

@app.get("/", response_class=HTMLResponse)
async def serve_index():
    index_file = STATIC_DIR / "index.html"
    if not index_file.exists():
        raise HTTPException(status_code=404, detail="index.html을 찾을 수 없습니다.")
    return FileResponse(index_file)

@app.post("/api/info")
async def fetch_info(req: ProcessRequest):
    """유튜브 링크 메타데이터만 빠르게 조회"""
    if not req.url or ("youtube" not in req.url and "youtu.be" not in req.url):
        raise HTTPException(status_code=400, detail="유효한 유튜브 URL을 입력해 주세요.")
    try:
        info = get_video_info(req.url)
        return {"success": True, "data": info}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"영상 정보를 가져오는 중 오류 발생: {str(e)}")

@app.post("/api/process")
async def process_youtube(req: ProcessRequest):
    """오디오 다운로드 + Gemini STT 수행"""
    if not req.url:
        raise HTTPException(status_code=400, detail="유튜브 URL을 입력해 주세요.")

    try:
        # 1. 오디오 다운로드
        audio_info = download_audio(req.url, str(DOWNLOADS_DIR))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"유튜브 오디오 다운로드 실패: {str(e)}")

    try:
        # 2. Gemini STT 전사 수행
        stt_result = transcribe_audio_file(
            file_path=audio_info["file_path"],
            mime_type=audio_info["mime_type"],
            model=req.model or "gemini-3.6-flash",
            prompt_instruction=req.prompt if req.prompt.strip() else None
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gemini 음성 전사(STT) 실패: {str(e)}")

    return {
        "success": True,
        "video": {
            "id": audio_info["id"],
            "title": audio_info["title"],
            "duration": audio_info["duration"],
            "thumbnail": audio_info["thumbnail"],
            "uploader": audio_info["uploader"],
            "file_size": audio_info["file_size"],
            "audio_url": f"/api/audio/{audio_info['file_name']}",
        },
        "transcript": stt_result["transcript"],
        "model": stt_result["model"],
    }

@app.get("/api/audio/{file_name}")
async def get_audio(file_name: str):
    """브라우저 오디오 재생을 위한 파일 스트리밍"""
    file_path = DOWNLOADS_DIR / file_name
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="오디오 파일을 찾을 수 없습니다.")
    
    ext = file_path.suffix.lstrip(".").lower()
    media_type = f"audio/{ext}"
    if ext == "m4a":
        media_type = "audio/mp4"
    return FileResponse(file_path, media_type=media_type)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
