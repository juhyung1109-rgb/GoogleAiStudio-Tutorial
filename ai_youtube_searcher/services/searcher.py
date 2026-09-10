import os
import json
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

def search_content_timestamp(query: str, segments: list, full_text: str = "") -> dict:
    """
    영상 내용 중 사용자가 입력한 검색어/주제와 일치하는 가장 적절한 시간(초)을 탐색
    1차: 로컬 키워드 일치 검색
    2차: gemini-3.8-flash 모델을 활용한 의미 기반 타임스탬프 탐색
    """
    if not query or not segments:
        return {"target_seconds": 0, "time_str": "00:00", "reason": "검색 결과가 없습니다.", "matches": []}

    # 1. 로컬 키워드 매칭
    keyword_matches = []
    q_lower = query.lower().strip()
    for seg in segments:
        text = seg.get("text", "")
        if q_lower in text.lower():
            keyword_matches.append({
                "seconds": seg.get("start_seconds", 0),
                "time_str": seg.get("time_str", "00:00"),
                "speaker": seg.get("speaker", ""),
                "text": text,
                "highlight": True
            })

    # 2. Gemini 3.8 Flash를 통한 지능형 타임스탬프 탐색
    client = get_client()
    target_model = "gemini-3.8-flash"

    context_lines = []
    for s in segments[:100]:
        context_lines.append(f"[{s.get('time_str')}] ({s.get('start_seconds')}s) {s.get('text')}")
    transcript_context = "\n".join(context_lines)

    prompt = f"""
당신은 동영상 타임스탬프 탐색 전문가입니다.
사용자가 찾고자 하는 내용: "{query}"

아래는 동영상의 타임스탬프별 대본입니다:
---
{transcript_context}
---

사용자가 찾는 내용이 시작되거나 가장 핵심적으로 다루어지는 시간(초 단위)을 찾아주세요.
반드시 아래 JSON 형식으로만 응답해주세요:
```json
{{
  "target_seconds": 125.0,
  "time_str": "02:05",
  "reason": "해당 내용이 시작되는 이유 및 설명 한 문장",
  "snippet": "해당 구간의 핵심 대사"
}}
```
"""

    try:
        response = client.models.generate_content(
            model=target_model,
            contents=prompt
        )
        res_text = response.text.strip()
        if "```" in res_text:
            res_text = res_text.split("```")[1]
            if res_text.startswith("json"):
                res_text = res_text[4:]
        ai_res = json.loads(res_text.strip())
        target_sec = float(ai_res.get("target_seconds", 0))
        t_str = ai_res.get("time_str", "00:00")
        reason = ai_res.get("reason", "검색된 위치입니다.")

        matches = []
        matches.append({
            "seconds": target_sec,
            "time_str": t_str,
            "speaker": "AI 추천 위치",
            "text": ai_res.get("snippet", reason),
            "highlight": True
        })
        for km in keyword_matches:
            if abs(km["seconds"] - target_sec) > 3:
                matches.append(km)

        return {
            "target_seconds": target_sec,
            "time_str": t_str,
            "reason": reason,
            "matches": matches[:10]
        }
    except Exception as e:
        print(f"Gemini 타임스탬프 탐색 실패: {e}")
        if keyword_matches:
            first = keyword_matches[0]
            return {
                "target_seconds": first["seconds"],
                "time_str": first["time_str"],
                "reason": f"키워드 '{query}'가 포함된 구간입니다.",
                "matches": keyword_matches[:10]
            }
        return {
            "target_seconds": 0,
            "time_str": "00:00",
            "reason": f"'{query}' 관련 내용을 찾지 못했습니다.",
            "matches": []
        }

def answer_question_with_gemini(question: str, transcript: str, video_title: str = "") -> dict:
    """
    gemini-3.8-flash 모델을 사용하여 트랜스크립트 기반 질의응답
    답변 내에 [MM:SS] 형식의 타임스탬프를 포함하도록 유도
    """
    client = get_client()
    target_model = "gemini-3.8-flash"

    prompt = f"""
당신은 동영상 내용 전문 AI 어시스턴트입니다.
사용자의 질문에 대해 아래 제공된 동영상 대본(타임스탬프 포함)을 기반으로 정확하고 친절하게 답변해주세요.

동영상 제목: {video_title}

[동영상 대본]:
{transcript[:8000]}

[사용자 질문]:
{question}

[지침]:
1. 대본에 나오는 사실에 근거하여 명확하고 이해하기 쉽게 답변하세요.
2. 답변 중 관련된 내용이나 증거가 나오는 부분에 반드시 [MM:SS] 형식의 타임스탬프를 함께 표기해주세요. (예: "고종은 창덕궁 인정전에서 [03:42]에 다음과 같이 선언했습니다.")
3. 사용자가 타임스탬프를 클릭하여 해당 영상 위치로 바로 이동할 수 있으므로, 타임스탬프 형식을 정확히 지켜주세요.
"""

    try:
        response = client.models.generate_content(
            model=target_model,
            contents=prompt
        )
        answer_text = response.text.strip()
    except Exception as e:
        print(f"gemini-3.8-flash Q&A 실패 ({e}), gemini-2.5-flash로 대체 시도...")
        target_model = "gemini-2.5-flash"
        response = client.models.generate_content(
            model=target_model,
            contents=prompt
        )
        answer_text = response.text.strip()

    timestamps = []
    found_times = re.findall(r"\[(\d{1,2}:\d{2})\]", answer_text)
    for ft in set(found_times):
        parts = ft.split(":")
        sec = int(parts[0]) * 60 + int(parts[1])
        timestamps.append({"time_str": ft, "seconds": sec})

    return {
        "model": target_model,
        "answer": answer_text,
        "timestamps": sorted(timestamps, key=lambda x: x["seconds"])
    }

def generate_summary_and_chapters(transcript: str, video_title: str = "", segments: list = None) -> dict:
    """
    gemini-3.8-flash 모델을 사용하여 3줄 핵심 요약 및 자동 챕터(목차) 생성
    """
    client = get_client()
    target_model = "gemini-3.8-flash"

    prompt = f"""
당신은 동영상 분석 및 요약 전문가입니다.
동영상 제목: "{video_title}"

아래는 동영상의 전체 대본과 타임스탬프입니다:
---
{transcript[:8000]}
---

위 내용을 분석하여:
1. 영상의 가장 중요한 핵심 내용을 명확한 3문장(3줄 요약)으로 작성해주세요.
2. 영상의 주요 흐름을 3~6개의 논리적인 타임라인 챕터(목차)로 나누어주세요. 각 챕터의 시작 시간(초, MM:SS), 챕터 제목, 간단한 설명을 작성해주세요.

반드시 아래 JSON 형식으로만 정확히 응답해주세요:
```json
{{
  "summary_points": [
    "첫 번째 핵심 요약 문장",
    "두 번째 핵심 요약 문장",
    "세 번째 핵심 요약 문장"
  ],
  "chapters": [
    {{
      "start_seconds": 0.0,
      "time_str": "00:00",
      "title": "도입부 및 주제 소개",
      "description": "챕터에 대한 간략한 1줄 설명"
    }},
    {{
      "start_seconds": 46.0,
      "time_str": "00:46",
      "title": "핵심 원인 분석",
      "description": "세부 내용 설명"
    }}
  ]
}}
```
"""

    try:
        response = client.models.generate_content(
            model=target_model,
            contents=prompt
        )
        res_text = response.text.strip()
        if "```" in res_text:
            res_text = res_text.split("```")[1]
            if res_text.startswith("json"):
                res_text = res_text[4:]
        data = json.loads(res_text.strip())
        return {
            "summary_points": data.get("summary_points", []),
            "chapters": data.get("chapters", [])
        }
    except Exception as e:
        print(f"요약 및 챕터 생성 오류: {e}")
        # fallback 기본 챕터 생성
        return {
            "summary_points": ["동영상 음성 분석이 완료되었습니다."],
            "chapters": [
                {"start_seconds": 0.0, "time_str": "00:00", "title": "영상 시작", "description": "전체 재생"}
            ]
        }
