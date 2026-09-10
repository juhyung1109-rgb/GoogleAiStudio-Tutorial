// YouTube IFrame Player API 및 상태 변수
let ytPlayer = null;
let isPlayerReady = false;
let currentVideoId = "";
let currentVideoInfo = null;
let transcriptionData = null;
let currentVolume = 70;
let isMuted = false;

// 1. YouTube IFrame API 로드
const tag = document.createElement("script");
tag.src = "https://www.youtube.com/iframe_api";
const firstScriptTag = document.getElementsByTagName("script")[0];
firstScriptTag.parentNode.insertBefore(tag, firstScriptTag);

window.onYouTubeIframeAPIReady = function () {
  console.log("YouTube IFrame API Ready");
};

function initOrLoadPlayer(videoId) {
  currentVideoId = videoId;
  const placeholder = document.getElementById("player-placeholder");
  if (placeholder) placeholder.style.display = "none";

  if (!ytPlayer) {
    ytPlayer = new YT.Player("yt-player", {
      height: "100%",
      width: "100%",
      videoId: videoId,
      playerVars: {
        autoplay: 1,
        playsinline: 1,
        rel: 0,
        modestbranding: 1,
      },
      events: {
        onReady: (event) => {
          isPlayerReady = true;
          event.target.setVolume(currentVolume);
          event.target.playVideo();
          startSyncTracker();
        },
      },
    });
  } else {
    ytPlayer.loadVideoById(videoId);
    ytPlayer.playVideo();
  }
}

// 2. 특정 시간으로 점프하여 영상 재생
function jumpToTime(seconds) {
  if (ytPlayer && typeof ytPlayer.seekTo === "function") {
    ytPlayer.seekTo(seconds, true);
    ytPlayer.playVideo();
    showToast(`영상 위치 ${formatTimeStr(seconds)} (으)로 이동하여 재생합니다.`);
  } else {
    console.warn("Player not ready yet.");
  }
}

function formatTimeStr(sec) {
  const s = Math.floor(sec);
  const m = Math.floor(s / 60);
  const remSec = s % 60;
  return `${m.toString().padStart(2, "0")}:${remSec.toString().padStart(2, "0")}`;
}

// 3. 음향 크기(볼륨) 조절
const volumeSlider = document.getElementById("volume-slider");
const volumeText = document.getElementById("volume-text");
const volumeMuteBtn = document.getElementById("volume-mute-btn");

if (volumeSlider) {
  volumeSlider.addEventListener("input", (e) => {
    currentVolume = parseInt(e.target.value, 10);
    volumeText.textContent = `${currentVolume}%`;
    if (ytPlayer && typeof ytPlayer.setVolume === "function") {
      if (isMuted && currentVolume > 0) {
        ytPlayer.unMute();
        isMuted = false;
        volumeMuteBtn.textContent = "🔊";
      }
      ytPlayer.setVolume(currentVolume);
    }
  });
}

if (volumeMuteBtn) {
  volumeMuteBtn.addEventListener("click", () => {
    if (!ytPlayer) return;
    if (isMuted) {
      ytPlayer.unMute();
      isMuted = false;
      volumeMuteBtn.textContent = "🔊";
      volumeSlider.value = currentVolume;
      volumeText.textContent = `${currentVolume}%`;
    } else {
      ytPlayer.mute();
      isMuted = true;
      volumeMuteBtn.textContent = "🔇";
      volumeSlider.value = 0;
      volumeText.textContent = "0%";
    }
  });
}

// 4. 유튜브 URL 검색 및 STT 분석 파이프라인
const topUrlInput = document.getElementById("top-url-input");
const topSearchBtn = document.getElementById("top-search-btn");
const statusBadge = document.getElementById("status-badge");
const videoTitleEl = document.getElementById("video-title");
const videoUploaderEl = document.getElementById("video-uploader");

topSearchBtn.addEventListener("click", () => handleUrlSubmit());
topUrlInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter") handleUrlSubmit();
});

async function handleUrlSubmit() {
  const url = topUrlInput.value.trim();
  if (!url) {
    alert("유튜브 동영상 링크를 입력해 주세요.");
    return;
  }

  // 1단계: 메타데이터 조회 & 즉시 영상 로드
  statusBadge.className = "status-badge";
  statusBadge.innerHTML = `<span class="spinner"></span> 영상 불러오는 중...`;

  try {
    const infoRes = await fetch("/api/video-info", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url }),
    });
    const infoData = await infoRes.json();

    if (!infoData.success) {
      alert("영상 정보를 가져올 수 없습니다.");
      statusBadge.textContent = "오류 발생";
      return;
    }

    currentVideoInfo = infoData.video;
    videoTitleEl.textContent = currentVideoInfo.title;
    videoUploaderEl.textContent = `${currentVideoInfo.uploader} • 길이: ${currentVideoInfo.duration_str}`;

    // 플레이어 즉시 실행
    initOrLoadPlayer(currentVideoInfo.id);

    // 2단계: 백그라운드 STT 및 타임스탬프 추출
    startAudioTranscribe(url);
  } catch (err) {
    console.error(err);
    alert("영상 처리 중 통신 오류가 발생했습니다.");
    statusBadge.textContent = "연결 오류";
  }
}

async function startAudioTranscribe(url) {
  statusBadge.className = "status-badge";
  statusBadge.innerHTML = `<span class="spinner"></span> Gemini 3.5 Transcribe 음성 분석 중...`;

  try {
    const res = await fetch("/api/transcribe", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url }),
    });
    const data = await res.json();

    if (data.success && data.transcription) {
      transcriptionData = data.transcription;
      statusBadge.className = "status-badge done";
      statusBadge.textContent = `✓ AI 분석 완료 (${data.transcription.model})`;
      
      // 대본 탭 렌더링
      renderTranscriptList(data.transcription.segments);

      // 챗봇 시스템 안내 메시지
      appendChatMessage("ai", `동영상 음성 분석이 완료되었습니다! <strong>전체 대본</strong> 탭에서 타임스탬프별 대사를 확인하시거나, 궁금한 점을 질문해보세요.`);
    } else {
      statusBadge.textContent = "분석 실패";
    }
  } catch (err) {
    console.error("Transcribe Error:", err);
    statusBadge.textContent = "분석 실패 (오류)";
  }
}

// 5. 영상 위 오버레이 빠른 검색창 & 사이드바 검색창
const overlayInput = document.getElementById("overlay-search-input");
const overlayBtn = document.getElementById("overlay-search-btn");

overlayBtn.addEventListener("click", () => handleContentSearch(overlayInput.value));
overlayInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter") handleContentSearch(overlayInput.value);
});

async function handleContentSearch(query) {
  if (!query || !query.trim()) {
    alert("검색할 영상 내용을 입력해주세요. (예: 인정전, 날씨)");
    return;
  }

  if (!transcriptionData || !transcriptionData.segments || transcriptionData.segments.length === 0) {
    alert("현재 영상의 AI 음성 분석이 진행 중입니다. 잠시 후 완료되면 다시 시도해 주세요.");
    return;
  }

  switchTab("search-tab");
  const searchResultsEl = document.getElementById("search-results-list");
  searchResultsEl.innerHTML = `<div style="text-align:center; padding:20px; color:#aaa;"><span class="spinner"></span> Gemini 3.8 Flash로 해당 내용의 타임스탬프를 탐색 중입니다...</div>`;

  try {
    const res = await fetch("/api/search", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        query: query.trim(),
        segments: transcriptionData.segments,
        full_text: transcriptionData.full_text || "",
      }),
    });
    const json = await res.json();

    if (json.success && json.data) {
      const data = json.data;
      renderSearchResults(data);

      // 가장 관련성 높은 위치로 즉시 자동 점프 & 재생!
      if (data.target_seconds !== undefined && data.target_seconds !== null) {
        jumpToTime(data.target_seconds);
      }
    } else {
      searchResultsEl.innerHTML = `<div style="color:#aaa; text-align:center; padding:20px;">일치하는 내용을 찾지 못했습니다.</div>`;
    }
  } catch (err) {
    console.error(err);
    searchResultsEl.innerHTML = `<div style="color:#ff6b6b; padding:20px;">검색 처리 중 오류가 발생했습니다.</div>`;
  }
}

function renderSearchResults(data) {
  const container = document.getElementById("search-results-list");
  container.innerHTML = "";

  if (data.reason) {
    const reasonEl = document.createElement("div");
    reasonEl.style.cssText = "background:rgba(62,166,255,0.1); border-left:3px solid #3ea6ff; padding:10px 12px; border-radius:4px; font-size:13px; color:#f1f1f1; margin-bottom:12px;";
    reasonEl.innerHTML = `<strong>💡 탐색 결과:</strong> ${escapeHtml(data.reason)} (<strong>${data.time_str}</strong>로 이동)`;
    container.appendChild(reasonEl);
  }

  if (!data.matches || data.matches.length === 0) {
    container.innerHTML += `<div style="color:#aaa; text-align:center; padding:10px;">상세 구간 매칭 항목이 없습니다.</div>`;
    return;
  }

  data.matches.forEach((item) => {
    const card = document.createElement("div");
    card.className = "result-card";
    card.onclick = () => jumpToTime(item.seconds);

    card.innerHTML = `
      <div style="display:flex; justify-content:space-between; align-items:center;">
        <span class="result-time-tag">⏱ ${item.time_str}</span>
        <span style="font-size:11px; color:#aaa;">${escapeHtml(item.speaker || "")}</span>
      </div>
      <div class="result-snippet">${escapeHtml(item.text)}</div>
      <div style="font-size:11px; color:#3ea6ff; margin-top:4px;">▶ 클릭하여 이 위치에서 재생</div>
    `;
    container.appendChild(card);
  });
}

// 6. 전체 대본 렌더링
function renderTranscriptList(segments) {
  const container = document.getElementById("transcript-list");
  container.innerHTML = "";

  if (!segments || segments.length === 0) {
    container.innerHTML = `<div style="text-align:center; padding:20px; color:#777;">추출된 대본이 없습니다.</div>`;
    return;
  }

  segments.forEach((seg, idx) => {
    const item = document.createElement("div");
    item.className = "transcript-item";
    item.id = `ts-item-${idx}`;
    item.dataset.seconds = seg.start_seconds;
    item.onclick = () => jumpToTime(seg.start_seconds);

    item.innerHTML = `
      <div class="transcript-time">${seg.time_str}</div>
      <div class="transcript-content">
        <div class="transcript-speaker">${escapeHtml(seg.speaker || "화자")}</div>
        <div>${escapeHtml(seg.text)}</div>
      </div>
    `;
    container.appendChild(item);
  });
}

// 현재 재생 시간과 대본 동기화
let activeIndex = -1;
function startSyncTracker() {
  setInterval(() => {
    if (!ytPlayer || !transcriptionData || !transcriptionData.segments) return;
    if (typeof ytPlayer.getCurrentTime !== "function") return;

    const currentSec = ytPlayer.getCurrentTime();
    const segments = transcriptionData.segments;
    let foundIdx = -1;

    for (let i = 0; i < segments.length; i++) {
      if (currentSec >= segments[i].start_seconds) {
        foundIdx = i;
      } else {
        break;
      }
    }

    if (foundIdx !== -1 && foundIdx !== activeIndex) {
      if (activeIndex !== -1) {
        const prev = document.getElementById(`ts-item-${activeIndex}`);
        if (prev) prev.classList.remove("current");
      }
      activeIndex = foundIdx;
      const curr = document.getElementById(`ts-item-${activeIndex}`);
      if (curr) {
        curr.classList.add("current");
        // 자동 스크롤
        curr.scrollIntoView({ behavior: "smooth", block: "nearest" });
      }
    }
  }, 500);
}

// 7. Gemini 3.8 Flash 대화형 Q&A
const chatInput = document.getElementById("chat-input");
const chatSendBtn = document.getElementById("chat-send-btn");
const chatMessages = document.getElementById("chat-messages");

chatSendBtn.addEventListener("click", () => handleChatSubmit());
chatInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter") handleChatSubmit();
});

async function handleChatSubmit() {
  const q = chatInput.value.trim();
  if (!q) return;

  if (!transcriptionData || !transcriptionData.full_text) {
    alert("동영상 음성 분석이 완료된 후 질문하실 수 있습니다.");
    return;
  }

  appendChatMessage("user", escapeHtml(q));
  chatInput.value = "";

  const loadingBubble = appendChatMessage("ai", `<span class="spinner"></span> Gemini 3.8 Flash가 영상 내용을 분석하여 답변을 작성하고 있습니다...`);

  try {
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        question: q,
        transcript: transcriptionData.full_text,
        video_title: currentVideoInfo ? currentVideoInfo.title : "",
      }),
    });
    const json = await res.json();

    if (json.success && json.data) {
      const answer = json.data.answer;
      loadingBubble.innerHTML = linkifyTimestamps(answer);
    } else {
      loadingBubble.textContent = "답변 생성에 실패했습니다.";
    }
  } catch (err) {
    console.error(err);
    loadingBubble.textContent = "네트워크 통신 중 오류가 발생했습니다.";
  }
}

function appendChatMessage(sender, htmlContent) {
  const bubble = document.createElement("div");
  bubble.className = `chat-bubble ${sender}`;
  bubble.innerHTML = htmlContent;
  chatMessages.appendChild(bubble);
  chatMessages.scrollTop = chatMessages.scrollHeight;
  return bubble;
}

// 답변 내 [MM:SS] 타임스탬프를 클릭 가능한 링크로 변환
function linkifyTimestamps(text) {
  const escaped = escapeHtml(text);
  return escaped.replace(/\[(\d{1,2}:\d{2})\]/g, (match, p1) => {
    const parts = p1.split(":");
    const sec = parseInt(parts[0], 10) * 60 + parseInt(parts[1], 10);
    return `<span class="ts-link" onclick="jumpToTime(${sec})">[${p1}]</span>`;
  });
}

// 8. 탭 전환 처리
window.switchTab = function (tabId) {
  document.querySelectorAll(".tab-btn").forEach((btn) => btn.classList.remove("active"));
  document.querySelectorAll(".tab-content").forEach((c) => c.classList.remove("active"));

  const targetBtn = document.querySelector(`.tab-btn[data-tab="${tabId}"]`);
  const targetContent = document.getElementById(tabId);

  if (targetBtn) targetBtn.classList.add("active");
  if (targetContent) targetContent.classList.add("active");
};

document.querySelectorAll(".tab-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    switchTab(btn.dataset.tab);
  });
});

// 토스트 메시지
function showToast(msg) {
  let toast = document.getElementById("toast-msg");
  if (!toast) {
    toast = document.createElement("div");
    toast.id = "toast-msg";
    toast.style.cssText = "position:fixed; bottom:24px; left:50%; transform:translateX(-50%); background:#323232; color:#fff; padding:10px 20px; border-radius:24px; font-size:13px; z-index:9999; box-shadow:0 4px 12px rgba(0,0,0,0.5); transition:opacity 0.3s;";
    document.body.appendChild(toast);
  }
  toast.textContent = msg;
  toast.style.opacity = "1";
  setTimeout(() => {
    toast.style.opacity = "0";
  }, 2500);
}

function escapeHtml(str) {
  if (!str) return "";
  return str
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}
