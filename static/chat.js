/* chat.js v7 — conversations + streaming + message actions + call mode */

const socket = io({ transports: ["websocket"] });

// ─── DOM refs ────────────────────────────────────────────────────────────
const chatArea     = document.getElementById("chatArea");
const inputBox     = document.getElementById("inputBox");
const sendBtn      = document.getElementById("sendBtn");
const stopSingBtn  = document.getElementById("stopSingBtn");
const statusText   = document.getElementById("status-text");
const statusDot    = document.getElementById("status-dot");
const quickRow     = document.getElementById("quickRow");
const glowCanvas   = document.getElementById("glowCanvas");
const ctx          = glowCanvas.getContext("2d");
const callBtn      = document.getElementById("callBtn");
const hangUpBtn    = document.getElementById("hangUpBtn");
const callBanner   = document.getElementById("callBanner");
const callTimer    = document.getElementById("callTimer");
const callSubtitle = document.getElementById("callSubtitle");
const inputArea    = document.getElementById("inputArea");
const micBtn       = document.getElementById("micBtn");

const CHAT_PAGE_I18N = {
  titles: {
    "zh-CN": "💕 灵魂伴侣",
    en: "💕 Soulmate",
  },
  strings: {
    "zh-CN": {
      app_name: "灵魂伴侣",
      logout: "退出",
      call_title: "打电话",
      voice_input_title: "语音输入",
      avatar_alt: "男友头像",
      status_online: "在线 · 等你说话",
      status_thinking: "思考中…",
      status_listening: "正在听…",
      status_call: "📞 通话中",
      status_call_processing: "📞 …",
      status_singing: "演唱《{title}》中…",
      stop_singing: "⏹ 停止唱歌",
      input_placeholder: "打字或按🎤说话…",
      input_listening_placeholder: "正在听…",
      empty_hint: "💕 和他打声招呼吧…",
      mic_listening: "🎤 我在听…",
      mic_no_speech: "没听到声音，再试一次？",
      mic_permission: "需要麦克风权限",
      reconnecting: "连接断开…正在重连",
      call_opening: "📞 我在呢，说吧…",
      call_end_comfort: "嗯…挂了也没关系，我一直在的 💕",
      call_permission: "🔇 请允许麦克风权限",
      call_network_retry: "网络问题，重试中…",
      call_hanging_up: "挂断中…",
      speech_unsupported: "⚠️ 浏览器不支持语音",
    },
    en: {
      app_name: "Soulmate",
      logout: "Logout",
      call_title: "Call",
      voice_input_title: "Voice Input",
      avatar_alt: "Companion Avatar",
      status_online: "Online · Ready to listen",
      status_thinking: "Thinking…",
      status_listening: "Listening…",
      status_call: "📞 In call",
      status_call_processing: "📞 Responding…",
      status_singing: "Singing “{title}”…",
      stop_singing: "⏹ Stop Singing",
      input_placeholder: "Type or tap the mic…",
      input_listening_placeholder: "Listening…",
      empty_hint: "💕 Say hi to him…",
      mic_listening: "🎤 I'm listening…",
      mic_no_speech: "Didn't catch that.",
      mic_permission: "Microphone permission needed",
      reconnecting: "Reconnecting…",
      call_opening: "📞 I'm here, go ahead…",
      call_end_comfort: "It's okay. I'm still here. 💕",
      call_permission: "🔇 Please allow microphone access",
      call_network_retry: "Network issue, retrying…",
      call_hanging_up: "Hanging up…",
      speech_unsupported: "⚠️ Speech not supported",
    },
  },
};

// ─── State ───────────────────────────────────────────────────────────────
let currentReqId = null;
let audioQueue = [];
let audioPlaying = false;
let currentAudio = null;
let glowAnimId = null;
let glowPhase = 0;
let currentGlowColor = null;
let audioUnlocked = false;
let typingRow = null;
let lastMsgTime = 0;
let recognition = null;
let isListening = false;
let currentStatusKey = "status_online";
let currentStatusVars = {};
let currentQuickPool = "default";
let currentCallSubtitleKey = "status_listening";
let currentCallSubtitleVars = {};

// conversation / streaming state
let conversationId = null;
let streamRow = null;       // bubble being streamed into
let streamText = "";
let streamedThisReq = false;

// call mode state
let callMode = false;
let callListening = false;
let callStartTime = 0;
let callTimerId = null;
let callRecognition = null;

const QUICK_POOLS = {
  default: [
    { send: "想你啦", label: { "zh-CN": "想你啦", en: "Miss you" } },
    { send: "在干嘛呢", label: { "zh-CN": "在干嘛呢", en: "What are you doing?" } },
    { send: "我今天好累", label: { "zh-CN": "我今天好累", en: "I'm tired today" } },
    { send: "陪我聊聊", label: { "zh-CN": "陪我聊聊", en: "Talk with me" } },
    { send: "睡不着…", label: { "zh-CN": "睡不着…", en: "Can't sleep" } },
    { send: "唱首歌吧", label: { "zh-CN": "唱首歌吧", en: "Sing for me" } },
  ],
  sleep: [
    { send: "嗯…晚安", label: { "zh-CN": "嗯…晚安", en: "Good night" } },
    { send: "再陪我一会", label: { "zh-CN": "再陪我一会", en: "Stay a bit longer" } },
    { send: "你也要睡了吗", label: { "zh-CN": "你也要睡了吗", en: "Are you sleeping too?" } },
  ],
  wake: [
    { send: "早安", label: { "zh-CN": "早安", en: "Good morning" } },
    { send: "睡醒了", label: { "zh-CN": "睡醒了", en: "I'm awake" } },
    { send: "做了个梦", label: { "zh-CN": "做了个梦", en: "I had a dream" } },
  ],
  sing: [
    { send: "换一首", label: { "zh-CN": "换一首", en: "Another song" } },
    { send: "唱你拿手的", label: { "zh-CN": "唱你拿手的", en: "Sing your best one" } },
  ],
};

const HANGUP_KEYWORDS = [
  "挂了吧", "先挂了", "挂了", "挂电话", "拜拜", "再见",
  "先不说了", "不说了", "挂断", "就这样吧", "先这样",
  "bye", "bye bye", "goodbye", "拜", "88",
];

const GLOW_COLORS = {
  pink: [[255, 107, 157], [181, 123, 238]],
  purple: [[181, 123, 238], [143, 83, 209]],
  call: [[255, 107, 157], [99, 102, 241]],
};

// ─── i18n helpers ────────────────────────────────────────────────────────
function getLang() {
  return window.VBF_I18N?.getLang?.() || "zh-CN";
}

function t(key, vars = {}) {
  const strings = CHAT_PAGE_I18N.strings[getLang()] || CHAT_PAGE_I18N.strings["zh-CN"];
  let text = strings[key] ?? key;
  Object.entries(vars).forEach(([name, value]) => {
    text = text.replaceAll(`{${name}}`, value);
  });
  return text;
}

// ─── generic utils ───────────────────────────────────────────────────────
function genReqId() {
  return Date.now().toString(36) + Math.random().toString(36).slice(2, 7);
}

function escHtml(s) {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function escAttr(s) {
  return s.replace(/&/g, "&amp;").replace(/"/g, "&quot;");
}

function setStatus(text, color) {
  statusText.textContent = text;
  statusText.style.color = color || "";
}

function setStatusLocalized(key, color, vars = {}) {
  currentStatusKey = key;
  currentStatusVars = vars;
  setStatus(t(key, vars), color);
}

function setCallSubtitleText(text) {
  currentCallSubtitleKey = null;
  currentCallSubtitleVars = {};
  callSubtitle.textContent = text;
}

function setCallSubtitleLocalized(key, vars = {}) {
  currentCallSubtitleKey = key;
  currentCallSubtitleVars = vars;
  callSubtitle.textContent = t(key, vars);
}

function setDot(state) {
  statusDot.className = "dot " + state;
}

function setBusy(busy) {
  sendBtn.disabled = busy;
  inputBox.disabled = busy;
  if (callBtn) callBtn.disabled = busy;
}

function updateInputPlaceholder() {
  inputBox.placeholder = isListening ? t("input_listening_placeholder") : t("input_placeholder");
}

function speechLocale() {
  return getLang() === "en" ? "en-US" : "zh-CN";
}

// ─── quick replies ───────────────────────────────────────────────────────
function updateQuickReplies(intent) {
  if (!quickRow) return;
  currentQuickPool = intent;
  const lang = getLang();
  const pool = QUICK_POOLS[intent] || QUICK_POOLS.default;
  quickRow.innerHTML = pool
    .map((item) => `<button class="quick-reply" data-send="${escAttr(item.send)}">${escHtml(item.label[lang] || item.label["zh-CN"])}</button>`)
    .join("");
  quickRow.querySelectorAll(".quick-reply").forEach((btn) => {
    btn.addEventListener("click", () => {
      inputBox.value = btn.dataset.send || btn.textContent;
      sendMessage();
    });
  });
}

// ─── glow ────────────────────────────────────────────────────────────────
function startGlow(colorName) {
  if (glowAnimId) cancelAnimationFrame(glowAnimId);
  currentGlowColor = colorName;
  glowPhase = 0;
  animateGlow();
}

function stopGlow() {
  if (glowAnimId) cancelAnimationFrame(glowAnimId);
  glowAnimId = null;
  currentGlowColor = null;
  ctx.clearRect(0, 0, 220, 220);
}

function animateGlow() {
  glowPhase += 0.04;
  const cx = 110;
  const cy = 110;
  ctx.clearRect(0, 0, 220, 220);

  if (currentGlowColor === "rainbow") {
    const hueBase = (glowPhase * 28) % 360;
    const layers = [88, 78, 68, 58, 48];
    layers.forEach((radius, i) => {
      const alpha = (1 - i / layers.length) * 0.14;
      const hue = (hueBase + i * 30) % 360;
      const grad = ctx.createRadialGradient(cx, cy, radius - 14, cx, cy, radius);
      grad.addColorStop(0, `hsla(${hue},100%,70%,0)`);
      grad.addColorStop(1, `hsla(${hue},100%,70%,${alpha})`);
      ctx.beginPath();
      ctx.arc(cx, cy, radius, 0, Math.PI * 2);
      ctx.fillStyle = grad;
      ctx.fill();
    });
    glowAnimId = requestAnimationFrame(animateGlow);
    return;
  }

  const pulse = (Math.sin(glowPhase) + 1) / 2;
  const cols = GLOW_COLORS[currentGlowColor] || GLOW_COLORS.pink;
  const [r1, r2] = cols;
  const interp = (a, b, x) => Math.round(a + (b - a) * x);
  const r = interp(r1[0], r2[0], pulse);
  const g = interp(r1[1], r2[1], pulse);
  const b = interp(r1[2], r2[2], pulse);

  [80, 70, 60, 50, 40].forEach((radius, i, arr) => {
    const alpha = (1 - i / arr.length) * 0.18;
    ctx.beginPath();
    ctx.arc(cx, cy, radius, 0, Math.PI * 2);
    ctx.fillStyle = `rgba(${r},${g},${b},${alpha})`;
    ctx.fill();
  });
  glowAnimId = requestAnimationFrame(animateGlow);
}

// ─── audio queue ─────────────────────────────────────────────────────────
function enqueueAudio(url, onEnded) {
  audioQueue.push({ url, onEnded: onEnded || null });
  if (!audioPlaying) dequeueAudio();
}

function dequeueAudio() {
  if (audioQueue.length === 0) {
    audioPlaying = false;
    currentAudio = null;
    if (currentGlowColor === "rainbow") stopGlow();
    if (callMode && !callListening) {
      setTimeout(() => startCallRecognition(), 600);
    }
    return;
  }

  audioPlaying = true;
  startGlow("rainbow");
  const item = audioQueue.shift();
  const audio = new Audio(item.url);
  currentAudio = audio;
  audio.onended = () => {
    if (item.onEnded) item.onEnded();
    dequeueAudio();
  };
  audio.onerror = () => {
    dequeueAudio();
  };
  audio.play().catch(() => {
    if (currentGlowColor === "rainbow") stopGlow();
    dequeueAudio();
    if (item.onEnded) item.onEnded();
  });
}

function stopAllAudio() {
  if (currentAudio) {
    currentAudio.pause();
    currentAudio = null;
  }
  audioQueue = [];
  audioPlaying = false;
}

// ─── time divider / typing / empty state ─────────────────────────────────
function formatTime(ts) {
  const d = new Date(ts);
  const h = d.getHours().toString().padStart(2, "0");
  const m = d.getMinutes().toString().padStart(2, "0");
  return `${h}:${m}`;
}

function maybeAddTimeDivider() {
  const now = Date.now();
  if (now - lastMsgTime > 300000 && chatArea.children.length > 0) {
    const div = document.createElement("div");
    div.className = "time-divider";
    div.innerHTML = `<span>${formatTime(now)}</span>`;
    chatArea.appendChild(div);
  }
  lastMsgTime = now;
}

function showTyping() {
  hideTyping();
  const row = document.createElement("div");
  row.className = "bubble-row bot typing-row";
  row.innerHTML = `
    <img class="bot-avatar" src="/static/avatar.png" alt="">
    <div class="typing-bubble">
      <div class="typing-dot"></div>
      <div class="typing-dot"></div>
      <div class="typing-dot"></div>
    </div>
  `;
  chatArea.appendChild(row);
  scrollBottom();
  typingRow = row;
}

function hideTyping() {
  if (typingRow) {
    typingRow.remove();
    typingRow = null;
  }
}

function addEmptyHint() {
  if (chatArea.querySelector(".bubble-row")) return;
  const hint = document.createElement("div");
  hint.className = "empty-hint";
  hint.textContent = t("empty_hint");
  chatArea.appendChild(hint);
}

function removeEmptyHint() {
  const hint = chatArea.querySelector(".empty-hint");
  if (hint) hint.remove();
}

function scrollBottom() {
  requestAnimationFrame(() => {
    chatArea.scrollTop = chatArea.scrollHeight;
  });
}

// ─── bubbles ─────────────────────────────────────────────────────────────
function addUserBubble(text) {
  removeEmptyHint();
  maybeAddTimeDivider();
  const row = document.createElement("div");
  row.className = "bubble-row user";
  row.innerHTML = `<div class="bubble">${escHtml(text)}</div>`;
  chatArea.appendChild(row);
  scrollBottom();
}

function addBotBubble(text, opts = {}) {
  hideTyping();
  removeEmptyHint();
  const row = document.createElement("div");
  row.className = "bubble-row bot";
  row.innerHTML = `<img class="bot-avatar" src="/static/avatar.png" alt=""><div class="bubble">${escHtml(text)}</div>`;
  chatArea.appendChild(row);
  decorateBubble(row, opts);
  scrollBottom();
  return row.querySelector(".bubble");
}

// ─── message actions (copy / replay audio / favorite / delete) ────────────
function decorateBubble(row, opts = {}) {
  const bubble = row.querySelector(".bubble");
  if (!bubble) return;
  if (opts.messageId) row.dataset.messageId = opts.messageId;
  if (opts.audioUrl) {
    row.dataset.audioUrl = opts.audioUrl;
    const play = document.createElement("button");
    play.className = "bubble-audio-btn";
    play.textContent = "▶";
    play.title = "播放语音";
    play.addEventListener("click", () => {
      if (currentAudio && !currentAudio.paused) {
        stopAllAudio();
        play.textContent = "▶";
      } else {
        unlockAudio();
        enqueueAudio(opts.audioUrl, () => { play.textContent = "▶"; });
        play.textContent = "⏸";
      }
    });
    bubble.appendChild(play);
  }
  const actions = document.createElement("div");
  actions.className = "bubble-actions";
  const copyBtn = document.createElement("button");
  copyBtn.textContent = "复制";
  copyBtn.addEventListener("click", () => {
    navigator.clipboard?.writeText(bubble.textContent.replace(/[▶⏸]|复制|收藏|删除/g, "").trim());
  });
  actions.appendChild(copyBtn);
  if (opts.messageId) {
    const favBtn = document.createElement("button");
    favBtn.textContent = "收藏";
    favBtn.addEventListener("click", () => {
      fetch(`/api/messages/${opts.messageId}/favorite`, { method: "POST" });
      favBtn.classList.toggle("active");
    });
    const delBtn = document.createElement("button");
    delBtn.textContent = "删除";
    delBtn.addEventListener("click", () => {
      fetch(`/api/messages/${opts.messageId}`, { method: "DELETE" })
        .then((r) => { if (r.ok) row.remove(); });
    });
    actions.appendChild(favBtn);
    actions.appendChild(delBtn);
  }
  row.appendChild(actions);
}

// ─── conversation history ────────────────────────────────────────────────
async function loadHistory() {
  try {
    const res = await fetch("/api/conversations/active");
    if (!res.ok) return;
    const data = await res.json();
    conversationId = data.id;
    (data.messages || []).forEach((m) => {
      if (m.role === "user") {
        removeEmptyHint();
        const row = document.createElement("div");
        row.className = "bubble-row user";
        row.innerHTML = `<div class="bubble">${escHtml(m.content)}</div>`;
        if (m.id) row.dataset.messageId = m.id;
        chatArea.appendChild(row);
      } else if (m.role === "assistant") {
        addBotBubble(m.content, { messageId: m.id, audioUrl: m.audio_url });
      }
    });
    if (data.messages && data.messages.length) {
      removeEmptyHint();
      lastMsgTime = Date.now();
      scrollBottom();
    }
  } catch (err) {
    console.log("[history] load failed", err);
  }
}

async function startNewConversation() {
  try {
    const res = await fetch("/api/conversations", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: "{}",
    });
    if (!res.ok) return;
    const data = await res.json();
    conversationId = data.id;
    chatArea.innerHTML = "";
    addEmptyHint();
  } catch (err) {
    console.log("[conversation] create failed", err);
  }
}

async function clearCurrentConversation() {
  if (!conversationId) return startNewConversation();
  if (!confirm("删除当前对话？聊天记录将被清除。")) return;
  try {
    await fetch(`/api/conversations/${conversationId}`, { method: "DELETE" });
  } catch (_) {}
  conversationId = null;
  await startNewConversation();
}

// ─── audio unlock ────────────────────────────────────────────────────────
let _unlockAudio = null;

function unlockAudio() {
  if (audioUnlocked) return;
  try {
    const AC = window.AudioContext || window.webkitAudioContext;
    if (AC) {
      _unlockAudio = _unlockAudio || new AC();
      if (_unlockAudio.state === "suspended") _unlockAudio.resume();
      const buf = _unlockAudio.createBuffer(1, 1, 22050);
      const src = _unlockAudio.createBufferSource();
      src.buffer = buf;
      src.connect(_unlockAudio.destination);
      src.start(0);
      const silent = new Audio("data:audio/wav;base64,UklGRigAAABXQVZFZm10IBIAAAABAAEARKwAAIhYAQACABAAAABkYXRhAgAAAAEA");
      silent.play().then(() => { silent.pause(); silent.remove(); }).catch(() => {});
    }
  } catch (_) {}
  audioUnlocked = true;
}

// ─── text mode ───────────────────────────────────────────────────────────
function callModeActive() {
  return callMode;
}

function sendMessage() {
  const text = inputBox.value.trim();
  if (!text || sendBtn.disabled) return;

  inputBox.value = "";
  addUserBubble(text);
  removeEmptyHint();
  unlockAudio();

  currentReqId = genReqId();
  streamedThisReq = false;
  streamRow = null;
  streamText = "";
  const event = callModeActive() ? "call_message" : "chat_message";
  setBusy(true);
  setDot("busy");
  setStatusLocalized("status_thinking", "#B57BEE");
  startGlow("pink");
  showTyping();

  socket.emit(event, { text, req_id: currentReqId, conversation_id: conversationId });
}

sendBtn.addEventListener("click", sendMessage);
inputBox.addEventListener("keydown", (e) => {
  if (e.key === "Enter") sendMessage();
});

function initSpeech() {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SpeechRecognition) {
    micBtn.style.display = "none";
    return;
  }

  recognition = new SpeechRecognition();
  recognition.lang = speechLocale();
  recognition.interimResults = true;
  recognition.continuous = false;
  recognition.maxAlternatives = 1;

  recognition.onresult = (e) => {
    let final = "";
    let interim = "";
    for (let i = e.resultIndex; i < e.results.length; i++) {
      const transcript = e.results[i][0].transcript;
      if (e.results[i].isFinal) final += transcript;
      else interim += transcript;
    }
    inputBox.value = final || interim;
    inputBox.focus();
  };

  recognition.onend = () => {
    stopListening();
    const text = inputBox.value.trim();
    if (text) sendMessage();
  };

  recognition.onerror = (e) => {
    console.log("[voice] error:", e.error);
    stopListening();
    if (e.error === "no-speech") {
      setStatusLocalized("mic_no_speech", "#FF6B9D");
    } else if (e.error === "not-allowed") {
      setStatusLocalized("mic_permission", "#FF6B9D");
    }
    setTimeout(() => setStatusLocalized("status_online", "#8B7AA0"), 2500);
  };
}

function startListening() {
  if (!recognition || isListening || sendBtn.disabled) return;
  isListening = true;
  recognition.lang = speechLocale();
  micBtn.classList.add("listening");
  updateInputPlaceholder();
  inputBox.value = "";
  setStatusLocalized("mic_listening", "#FF6B9D");
  startGlow("pink");
  recognition.start();
}

function stopListening() {
  if (!isListening) return;
  isListening = false;
  micBtn.classList.remove("listening");
  updateInputPlaceholder();
  try {
    recognition.stop();
  } catch (_) {}
}

micBtn.addEventListener("click", () => {
  if (isListening) {
    stopListening();
    const text = inputBox.value.trim();
    if (text) sendMessage();
  } else {
    startListening();
  }
});

// ─── call mode ───────────────────────────────────────────────────────────
function toggleCallMode() {
  if (callMode) hangUpCall();
  else startCall();
}

function startCall() {
  callMode = true;
  callListening = false;
  callStartTime = Date.now();

  document.body.classList.add("call-mode");
  callBanner.classList.remove("hidden");
  hangUpBtn.classList.remove("hidden");
  callBtn.classList.add("active");
  inputArea.classList.add("hidden");

  updateCallTimer();
  callTimerId = setInterval(updateCallTimer, 1000);

  callRecognition = initCallRecognition();
  if (callRecognition) startCallRecognition();

  setCallSubtitleLocalized("status_listening");
  setStatusLocalized("status_call", "#FF6B9D");
  setDot("busy");
  startGlow("call");
  addBotBubble(t("call_opening"));
}

function hangUpCall() {
  callMode = false;
  callListening = false;
  callRecognition = null;

  stopCallRecognition();
  stopAllAudio();

  document.body.classList.remove("call-mode");
  callBanner.classList.add("hidden");
  hangUpBtn.classList.add("hidden");
  callBtn.classList.remove("active");
  inputArea.classList.remove("hidden");

  if (callTimerId) {
    clearInterval(callTimerId);
    callTimerId = null;
  }

  stopGlow();
  setStatusLocalized("status_online", "#8B7AA0");
  setDot("idle");
  callSubtitle.textContent = "";

  setBusy(false);
  hideTyping();
  addBotBubble(t("call_end_comfort"));
}

function updateCallTimer() {
  const elapsed = Math.floor((Date.now() - callStartTime) / 1000);
  const m = Math.floor(elapsed / 60).toString().padStart(2, "0");
  const s = (elapsed % 60).toString().padStart(2, "0");
  callTimer.textContent = `${m}:${s}`;
}

function initCallRecognition() {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SpeechRecognition) {
    callSubtitle.textContent = t("speech_unsupported");
    return null;
  }

  const rec = new SpeechRecognition();
  rec.lang = speechLocale();
  rec.interimResults = true;
  rec.continuous = false;
  rec.maxAlternatives = 1;

  rec.onstart = () => {
    callListening = true;
    setCallSubtitleLocalized("status_listening");
    callSubtitle.classList.remove("listening");
  };

  rec.onresult = (e) => {
    let final = "";
    let interim = "";
    for (let i = e.resultIndex; i < e.results.length; i++) {
      const transcript = e.results[i][0].transcript;
      if (e.results[i].isFinal) final += transcript;
      else interim += transcript;
    }
    const display = final || interim;
    if (display) {
      setCallSubtitleText(display);
      callSubtitle.classList.add("listening");
    }
  };

  rec.onerror = (e) => {
    console.log("[call] speech error:", e.error);
    callListening = false;
    if (e.error === "not-allowed") {
      setCallSubtitleLocalized("call_permission");
      return;
    }
    if (e.error === "no-speech") {
      setCallSubtitleLocalized("status_listening");
    } else if (e.error === "network") {
      setCallSubtitleLocalized("call_network_retry");
    } else {
      setCallSubtitleText("…");
    }

    if (callMode && e.error !== "not-allowed") {
      setTimeout(() => {
        if (callMode && !callListening && !audioPlaying) startCallRecognition();
      }, 800);
    }
  };

  rec.onend = () => {
    callListening = false;
    const text = (callSubtitle.textContent || "").trim();
    const lower = text.toLowerCase();
    if (HANGUP_KEYWORDS.some((kw) => lower.includes(kw.toLowerCase())) && text.length < 12) {
      setCallSubtitleLocalized("call_hanging_up");
      setTimeout(() => hangUpCall(), 300);
      return;
    }

    if (
      text &&
      text !== t("status_listening") &&
      text !== "…" &&
      !text.startsWith("🔇") &&
      !text.startsWith("⚠️")
    ) {
      sendCallMessage(text);
      return;
    }

    if (callMode && !audioPlaying) {
      setTimeout(() => {
        if (callMode && !callListening && !audioPlaying) startCallRecognition();
      }, 500);
    }
  };

  return rec;
}

function startCallRecognition() {
  if (!callRecognition || callListening || !callMode) return;
  callRecognition.lang = speechLocale();
  try {
    callRecognition.start();
  } catch (_) {
    try { callRecognition.abort(); } catch (_) {}
    callListening = false;
    if (callMode) setTimeout(() => startCallRecognition(), 300);
  }
}

function stopCallRecognition() {
  callListening = false;
  if (callRecognition) {
    try { callRecognition.abort(); } catch (_) {}
  }
}

function sendCallMessage(text) {
  if (!text || !callMode) return;

  callListening = false;
  stopCallRecognition();

  currentReqId = genReqId();
  addUserBubble(text);

  setCallSubtitleText("…");
  callSubtitle.classList.remove("listening");
  setDot("busy");
  setStatusLocalized("status_call_processing", "#B57BEE");
  showTyping();

  socket.emit("call_message", { text, req_id: currentReqId, conversation_id: conversationId });
}

callBtn.addEventListener("click", toggleCallMode);
hangUpBtn.addEventListener("click", hangUpCall);

// ─── sockets ─────────────────────────────────────────────────────────────
// streaming events
socket.on("assistant_message_start", (data) => {
  if (data.req_id !== currentReqId) return;
  if (data.conversation_id) conversationId = data.conversation_id;
  hideTyping();
  removeEmptyHint();
  streamText = "";
  streamedThisReq = true;
  const row = document.createElement("div");
  row.className = "bubble-row bot streaming";
  row.innerHTML = `<img class="bot-avatar" src="/static/avatar.png" alt=""><div class="bubble"><span class="stream-text"></span><span class="stream-cursor">▍</span></div>`;
  chatArea.appendChild(row);
  streamRow = row;
  scrollBottom();
});

socket.on("assistant_message_delta", (data) => {
  if (data.req_id !== currentReqId || !streamRow) return;
  streamText += data.delta || "";
  const span = streamRow.querySelector(".stream-text");
  if (span) span.textContent = streamText;
  scrollBottom();
});

socket.on("assistant_message_done", (data) => {
  if (data.req_id !== currentReqId) return;
  if (data.conversation_id) conversationId = data.conversation_id;
  const msg = data.message || {};
  if (streamRow) {
    const bubble = streamRow.querySelector(".bubble");
    bubble.innerHTML = escHtml(msg.content || streamText);
    streamRow.classList.remove("streaming");
    decorateBubble(streamRow, { messageId: msg.id, audioUrl: msg.audio_url });
    streamRow = null;
  } else if (msg.content) {
    addBotBubble(msg.content, { messageId: msg.id, audioUrl: msg.audio_url });
    streamedThisReq = true;
  }
  if (msg.audio_url && !callMode) enqueueAudio(msg.audio_url);
});

socket.on("assistant_message_error", (data) => {
  if (data.req_id !== currentReqId) return;
  hideTyping();
  if (streamRow) { streamRow.remove(); streamRow = null; }
});

socket.on("dialog_state", (data) => {
  if (data.req_id && data.req_id !== currentReqId) return;
  const stateKeyMap = {
    thinking: "status_thinking",
    generating_voice: "status_thinking",
    singing: "status_singing",
  };
  const key = stateKeyMap[data.state];
  if (key && key !== "status_singing") setStatusLocalized(key, "#B57BEE");
});

socket.on("song_card", (data) => {
  if (data.req_id !== currentReqId) return;
  // 状态由 singing_start / song_ready / singing_end 驱动 UI，这里仅记录
  console.log("[song]", data.status, data.title || "");
});

socket.on("call_reply", (data) => {
  if (data.req_id !== currentReqId) return;
  hideTyping();
  addBotBubble(data.text || "");
  startGlow("call");
  setCallSubtitleText(data.text || "");
  callSubtitle.classList.remove("listening");
  if (data.audio_url) enqueueAudio(data.audio_url);
});

socket.on("call_done", (data) => {
  if (data.req_id !== currentReqId) return;
  setDot("busy");
  setStatusLocalized("status_call", "#FF6B9D");
});

socket.on("status", (data) => {
  if (data.req_id !== currentReqId) return;
  if (data.key) {
    setStatusLocalized(data.key, data.color, data.params || {});
  } else {
    setStatus(data.text || "", data.color);
  }
});

socket.on("bot_message", (data) => {
  if (data.req_id !== currentReqId) return;
  hideTyping();
  startGlow(data.glow || "pink");
  if (streamedThisReq) {
    // 流式气泡已渲染并播放音频，避免重复
    streamedThisReq = false;
    return;
  }
  addBotBubble(data.text || "", { messageId: data.message_id, audioUrl: data.audio_url });
  if (data.audio_url) enqueueAudio(data.audio_url);
});

socket.on("singing_start", (data) => {
  if (data.req_id !== currentReqId) return;
  stopSingBtn.classList.remove("hidden");
  setDot("singing");
  setStatusLocalized("status_singing", "#B57BEE", { title: data.title || "歌曲" });
  startGlow("purple");
});

socket.on("song_ready", (data) => {
  if (data.req_id !== currentReqId) return;
  const title = data.title || "歌曲";
  hideTyping();
  const bubbles = chatArea.querySelectorAll(".bubble-row.bot .bubble");
  if (bubbles.length) {
    const last = bubbles[bubbles.length - 1];
    const label = document.createElement("div");
    label.className = "sing-label";
    label.textContent = `🎵 《${title}》`;
    last.appendChild(label);
  }
  enqueueAudio(data.audio_url, () => {
    stopSingBtn.classList.add("hidden");
    setDot("idle");
    setStatusLocalized("status_online", "#8B7AA0");
  });
});

socket.on("singing_end", (data) => {
  if (data.req_id !== currentReqId) return;
  stopSingBtn.classList.add("hidden");
  setDot("idle");
});

socket.on("server_done", (data) => {
  if (data.req_id !== currentReqId) return;
  if (callMode) return;
  setTimeout(() => {
    setBusy(false);
    if (!audioPlaying && audioQueue.length === 0) {
      stopGlow();
      setDot("idle");
      setStatusLocalized("status_online", "#8B7AA0");
      hideTyping();
    }
  }, 400);
});

stopSingBtn.addEventListener("click", () => {
  if (!currentReqId) return;
  const oldReqId = currentReqId;
  socket.emit("stop_singing", { req_id: oldReqId });

  stopAllAudio();
  stopSingBtn.classList.add("hidden");
  stopGlow();

  currentReqId = genReqId();
  setBusy(true);
  setDot("busy");
  setStatusLocalized("status_thinking", "#B57BEE");
  startGlow("pink");
  showTyping();
  socket.emit("singing_stopped", { req_id: currentReqId });
});

socket.on("disconnect", () => {
  setStatusLocalized("reconnecting", "#FF6B9D");
  setDot("idle");
});

socket.on("connect", () => {
  setStatusLocalized("status_online", "#8B7AA0");
  setDot("idle");
});

// ─── rerender after language change ──────────────────────────────────────
function rerenderLocalizedUi() {
  updateInputPlaceholder();
  updateQuickReplies(currentQuickPool);
  const hint = chatArea.querySelector(".empty-hint");
  if (hint) hint.textContent = t("empty_hint");
  if (currentStatusKey) {
    statusText.textContent = t(currentStatusKey, currentStatusVars);
  }
  if (currentCallSubtitleKey && !callBanner.classList.contains("hidden")) {
    callSubtitle.textContent = t(currentCallSubtitleKey, currentCallSubtitleVars);
  }
}

// ─── init ────────────────────────────────────────────────────────────────
VBF_I18N.mount({
  dict: CHAT_PAGE_I18N,
  onRender: rerenderLocalizedUi,
});
initSpeech();
updateInputPlaceholder();
addEmptyHint();
updateQuickReplies("default");

const newConvBtn = document.getElementById("newConvBtn");
if (newConvBtn) newConvBtn.addEventListener("click", clearCurrentConversation);

loadHistory();
