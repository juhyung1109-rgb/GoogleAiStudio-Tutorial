# YouTube Audio Downloader & Gemini STT Web Service

유튜브 동영상 링크를 입력하면 오디오를 다운로드하고, Gemini AI 모델을 통해 고품질의 음성 트랜스크립트(대본)를 생성하는 웹 서비스입니다.

---

## 1. 주요 기능
- **유튜브 오디오 다운로드**: `yt-dlp`를 활용하여 원본 오디오 스트림(m4a/webm 등)을 빠르게 추출 및 다운로드
- **Gemini STT 변환**: Google GenAI 최신 SDK(`google-genai`)를 활용하여 음성 내용을 타임스탬프 및 화자 분리와 함께 텍스트로 변환
- **웹 인터페이스**: 모던 반응형 SPA UI (Tailwind CSS 기반)
- **오디오 플레이어**: 추출된 음원을 브라우저에서 바로 감상 및 로컬 다운로드 가능
- **트랜스크립트 내보내기**: 원클릭 클립보드 복사 및 `.txt` 텍스트 파일 저장 기능 지원

---

## 2. 실행 방법

### (1) 의존성 패키지 설치
```bash
pip install -r requirements.txt
```

### (2) 환경 변수 설정
`.env` 파일에 Gemini API 키를 입력하거나 터미널에서 환경 변수를 등록합니다.
```powershell
$env:GEMINI_API_KEY="본인의_GEMINI_API_키"
```

### (3) 웹 서버 실행
```bash
python app.py
```
또는
```bash
uvicorn app:app --host 0.0.0.0 --port 8000 --reload
```

### (4) 웹 브라우저 접속
웹 브라우저를 열고 다음 주소로 이동합니다:
**`http://localhost:8000`**
