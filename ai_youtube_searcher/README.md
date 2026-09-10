# AI 유튜브 검색기 (AI YouTube Searcher)

유튜브 영상 링크를 입력하여 영상을 재생하고, 오디오를 다운로드하여 Gemini 모델로 전사 및 분석한 뒤, 특정 내용 검색 시 해당 위치로 점프 재생 및 Gemini 3.8 Flash 기반 질의응답을 제공하는 서비스입니다.

## ✨ 주요 기능
1. **유튜브 스타일 상단 헤더**:
   - YouTube KR 로고 및 중앙 유튜브 링크 검색창
   - 마이크, 만들기, 알림 버튼 제거된 깔끔한 상단 바
2. **동영상 플레이어 & 오버레이 검색창**:
   - 링크 입력 즉시 YouTube IFrame Player로 재생
   - 영상 위에 반투명 검색창을 통해 원하는 주제/내용을 검색하면 해당 시간대로 즉시 점프 및 재생
3. **음향 크기(볼륨) 조절 기능**:
   - 실시간 볼륨 슬라이더 (0~100%) 및 음소거 토글
4. **Gemini 3.5 Transcribe 음성 전사**:
   - 유튜브 오디오 다운로드 후 초/분 단위 타임스탬프와 화자 분리 전사
   - JSON 캐싱으로 재요청 시 초고속 로드
5. **Gemini 3.8 Flash 동영상 질의응답 (Q&A)**:
   - 영상 내용에 대해 질문하면 대본을 기반으로 정확한 답변과 타임스탬프 링크 제공
   - 타임스탬프 클릭 시 즉시 해당 위치로 영상 이동

## 🚀 실행 방법
`run.bat` 파일을 더블 클릭하거나 콘솔에서 다음 명령어를 실행합니다:
```bash
cd ai_youtube_searcher
call C:\Users\juhyung\miniconda\Scripts\activate.bat myenv
python -m uvicorn app:app --host 0.0.0.0 --port 8001 --reload
```
브라우저에서 `http://localhost:8001` 로 접속합니다.
