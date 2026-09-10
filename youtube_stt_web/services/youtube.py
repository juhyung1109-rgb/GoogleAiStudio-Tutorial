import os
import re
import yt_dlp

def sanitize_filename(name: str) -> str:
    return re.sub(r'[\\/*?:"<>|]', "", name).strip()

def get_video_info(url: str) -> dict:
    """유튜브 영상의 메타데이터(제목, 썸네일, 길이 등)를 추출합니다."""
    ydl_opts = {
        'extract_flat': True,
        'skip_download': True,
        'quiet': True,
        'no_warnings': True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        return {
            'id': info.get('id', ''),
            'title': info.get('title', 'Unknown Title'),
            'thumbnail': info.get('thumbnail', ''),
            'duration': info.get('duration', 0),
            'uploader': info.get('uploader', info.get('channel', 'Unknown')),
        }

def download_audio(url: str, output_dir: str) -> dict:
    """유튜브 영상의 오디오를 다운로드하여 저장 경로를 반환합니다."""
    os.makedirs(output_dir, exist_ok=True)
    
    # 1. 먼저 메타데이터 추출
    with yt_dlp.YoutubeDL({'quiet': True, 'no_warnings': True}) as ydl:
        info = ydl.extract_info(url, download=False)
        video_id = info.get('id', 'audio')
        title = info.get('title', 'unknown')
        duration = info.get('duration', 0)
        thumbnail = info.get('thumbnail', '')
        uploader = info.get('uploader', info.get('channel', 'Unknown'))

    # 파일 템플릿: video_id.%(ext)s 로 고정하여 안전하게 관리
    out_tmpl = os.path.join(output_dir, f"{video_id}.%(ext)s")
    
    # 2. 오디오 다운로드 (m4a, webm 등 가장 호환성 좋은 오디오 스트림 추출)
    ydl_opts = {
        'format': 'bestaudio[ext=m4a]/bestaudio/best',
        'outtmpl': out_tmpl,
        'noplaylist': True,
        'quiet': True,
        'no_warnings': True,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])

    # 생성된 파일 탐색 (확장자가 m4a, webm, mp3 등 다양할 수 있음)
    downloaded_file = None
    for ext in ['m4a', 'webm', 'mp3', 'opus', 'wav']:
        candidate = os.path.join(output_dir, f"{video_id}.{ext}")
        if os.path.exists(candidate):
            downloaded_file = candidate
            break

    if not downloaded_file:
        # 혹시 다른 확장자로 저장되었는지 디렉토리 검색
        for fname in os.listdir(output_dir):
            if fname.startswith(video_id):
                downloaded_file = os.path.join(output_dir, fname)
                break

    if not downloaded_file or not os.path.exists(downloaded_file):
        raise FileNotFoundError(f"오디오 파일을 다운로드할 수 없습니다: {url}")

    ext = os.path.splitext(downloaded_file)[1].lstrip('.').lower()
    mime_type_map = {
        'm4a': 'audio/mp4',
        'mp4': 'audio/mp4',
        'webm': 'audio/webm',
        'mp3': 'audio/mp3',
        'wav': 'audio/wav',
        'ogg': 'audio/ogg',
        'opus': 'audio/opus',
    }
    mime_type = mime_type_map.get(ext, 'audio/mp4')

    return {
        'id': video_id,
        'title': title,
        'duration': duration,
        'thumbnail': thumbnail,
        'uploader': uploader,
        'file_path': downloaded_file,
        'file_name': os.path.basename(downloaded_file),
        'mime_type': mime_type,
        'file_size': os.path.getsize(downloaded_file),
    }
