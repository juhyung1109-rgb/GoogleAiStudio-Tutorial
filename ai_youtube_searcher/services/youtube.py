import re
import os
from pathlib import Path
import yt_dlp

def extract_video_id(url: str) -> str:
    """다양한 형식의 유튜브 URL에서 11자리 비디오 ID 추출"""
    if not url:
        return ""
    patterns = [
        r"(?:v=|\/)([0-9A-Za-z_-]{11}).*",
        r"youtu\.be\/([0-9A-Za-z_-]{11})",
        r"embed\/([0-9A-Za-z_-]{11})",
        r"shorts\/([0-9A-Za-z_-]{11})"
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    if len(url.strip()) == 11 and re.match(r"^[0-9A-Za-z_-]{11}$", url.strip()):
        return url.strip()
    return ""

def format_duration(seconds: int) -> str:
    """초 단위를 MM:SS 또는 HH:MM:SS 로 포맷팅"""
    if not seconds:
        return "00:00"
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    if h > 0:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"

def get_video_info(url: str) -> dict:
    """영상 다운로드 없이 메타데이터(제목, 채널, 썸네일, 길이 등)만 추출"""
    video_id = extract_video_id(url)
    clean_url = f"https://www.youtube.com/watch?v={video_id}" if video_id else url

    ydl_opts = {
        'skip_download': True,
        'quiet': True,
        'no_warnings': True,
        'extract_flat': False,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(clean_url, download=False)
        vid = info.get("id") or video_id
        duration_sec = info.get("duration") or 0
        return {
            "id": vid,
            "url": f"https://www.youtube.com/watch?v={vid}",
            "title": info.get("title", "알 수 없는 제목"),
            "uploader": info.get("uploader", "알 수 없는 채널"),
            "duration": duration_sec,
            "duration_str": format_duration(duration_sec),
            "thumbnail": info.get("thumbnail") or f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg",
            "view_count": info.get("view_count", 0),
            "description": (info.get("description") or "")[:300]
        }

def download_audio(url: str, output_dir: str) -> dict:
    """유튜브에서 오디오를 추출하여 파일로 저장 (이미 있으면 캐시 반환)"""
    info = get_video_info(url)
    video_id = info["id"]
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # 이미 다운로드된 m4a 또는 mp3 파일이 있는지 확인
    for ext in ["m4a", "mp3", "webm", "opus"]:
        existing = output_path / f"{video_id}.{ext}"
        if existing.exists() and existing.stat().st_size > 1024:
            return {
                **info,
                "file_path": str(existing.resolve()),
                "file_name": existing.name,
                "file_size": existing.stat().st_size,
                "mime_type": f"audio/{ext}" if ext != "m4a" else "audio/mp4",
                "cached": True
            }

    # 다운로드 설정
    outtmpl = str(output_path / f"{video_id}.%(ext)s")
    ydl_opts = {
        'format': 'bestaudio[ext=m4a]/bestaudio/best',
        'outtmpl': outtmpl,
        'quiet': True,
        'no_warnings': True,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([f"https://www.youtube.com/watch?v={video_id}"])

    # 생성된 파일 탐색
    for ext in ["m4a", "mp3", "webm", "opus"]:
        created = output_path / f"{video_id}.{ext}"
        if created.exists():
            return {
                **info,
                "file_path": str(created.resolve()),
                "file_name": created.name,
                "file_size": created.stat().st_size,
                "mime_type": f"audio/{ext}" if ext != "m4a" else "audio/mp4",
                "cached": False
            }

    # fallback: 디렉토리 내 video_id로 시작하는 파일 찾기
    for p in output_path.glob(f"{video_id}.*"):
        if p.is_file():
            return {
                **info,
                "file_path": str(p.resolve()),
                "file_name": p.name,
                "file_size": p.stat().st_size,
                "mime_type": "audio/mp4",
                "cached": False
            }

    raise FileNotFoundError(f"오디오 파일 다운로드에 실패했습니다. ID: {video_id}")
