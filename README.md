# Voice Companion Agent — AI Native Companion Chat App

> **An AI-native companion chat app MVP**: persona-driven conversation, long-term memory, streaming replies, voice companionship, AI singing, and an emotion-aware dialog state machine — built on Flask + SocketIO + Claude.

[中文文档 / Chinese README](README_CN.md)

## ✨ What it does

- 💬 **Chat-app-grade messaging** — message bubbles, streaming token-by-token replies, history that survives refresh, conversation management (new / archive / delete)
- 🧠 **Long-term memory** — LLM-powered structured extraction into 6 memory types (`profile / preference / episodic / emotional / relationship / task`) with importance & confidence scoring, dedup, recall and user-controlled deletion
- 🗣️ **Voice companionship** — every reply gets a TTS audio asset (edge-tts → optional RVC voice conversion), replayable per message
- 📞 **Call mode** — phone-like UI, fast short replies, speech recognition input, hang-up keywords
- 🎵 **AI singing** — cancellable cloud RVC singing tasks (Replicate) with song matching and status tracking
- 😴 **Sleep mode** — soft, slow, question-free wind-down replies
- 🎭 **Emotion-aware** — rule-based emotion analysis auto-switches to comfort mode; dialog state machine drives UI states

## 🏗️ Architecture

```
voice-companion-agent/
├── web_app.py                 # entry point: python web_app.py
├── app/
│   ├── main.py                # app factory (Flask + SocketIO wiring)
│   ├── api/                   # REST blueprints: auth / chat / audio / admin
│   ├── websocket/             # SocketIO events: chat (streaming) / call / sing / presence
│   ├── services/              # business logic
│   │   ├── chat_service.py    #   ← the orchestrator (one chat turn pipeline)
│   │   ├── llm_service.py     #   Claude wrapper: complete / stream / classify_json
│   │   ├── memory_service.py  #   LLM structured memory extraction + lifecycle
│   │   ├── tts_service.py     #   unified TTS + audio asset bookkeeping
│   │   ├── singing_service.py #   async cancellable singing tasks
│   │   └── ...                #   user / conversation / message / safety
│   ├── agents/                # AI-native components
│   │   ├── intent_router.py   #   14 intents: rules → LLM JSON → cache → fallback
│   │   ├── prompt_builder.py  #   5-layer prompt: persona/user/conversation/memory/policy
│   │   ├── dialog_state_machine.py  # 10 states × 16 events
│   │   ├── memory_retriever.py      # similarity + importance + recency scoring
│   │   ├── emotion_analyzer.py
│   │   └── response_policy.py       # per-mode reply knobs
│   ├── repositories/          # SQLite persistence (no SQL in business layer)
│   ├── models/schemas.py      # typed dataclasses
│   ├── config/settings.py     # env-driven settings + production safety checks
│   └── utils/                 # logger (secret-redacting) / security / ids / time
├── templates/  static/        # mobile-first web UI
├── tests/                     # pytest suite (44 tests)
└── migrations/                # legacy data import
```

**Chat turn pipeline** (`chat_service.run_chat_turn`):

```
user text ──► IntentRouter ──► EmotionAnalyzer ──► persist user message
          ──► PromptBuilder (persona + memories + policy)
          ──► Claude streaming ──► assistant_message_start/delta/done events
          ──► persist assistant message ──► TTS audio asset
          ──► async memory extraction ──► user_states updated
```

## 🗃️ Data model (SQLite)

| Table | Purpose |
|---|---|
| `users` | hashed credentials, roles, display names |
| `conversations` | per-user sessions with mode / archive flags |
| `messages` | every message persisted: role, content_type (text/voice/song/card), intent, state, metadata |
| `memories` | 6-type long-term memory with importance (1-5), confidence (0-1), soft delete |
| `audio_assets` | every generated clip: type, path, public URL, provider |
| `user_states` | dialog state, emotional state, sleep/call mode flags |

Lightweight versioned migrations live in `app/repositories/db.py`; legacy `logs/conversations.db` can be imported with `python migrations/import_legacy_logs.py`.

## 🚀 Getting started

```bash
git clone https://github.com/GitGPT-jpg/voice-companion-agent.git
cd voice-companion-agent
pip install -r requirements.txt
cp .env.example .env        # fill in ANTHROPIC_API_KEY etc.
python web_app.py           # → http://localhost:5000
```

Run tests:

```bash
pytest
```

## 🔐 Security & privacy

- Production startup checks: refuses `insecure-dev-key` secrets and `admin/admin` credentials when `APP_ENV=production`
- Hashed passwords in DB, login throttling (5 failures / 5 min), HttpOnly + SameSite cookies
- Per-user data isolation across messages / memories / audio; path-traversal-safe audio serving
- Secret-redacting logger; user data export (`GET /api/export`), conversation deletion, memory clearing

## ⚙️ Environment variables

See [.env.example](.env.example) — key ones: `APP_ENV`, `WEB_SECRET_KEY`, `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL`, `TTS_PROVIDER`, `REPLICATE_API_KEY`, feature flags `ENABLE_SINGING` / `ENABLE_MEMORY_EXTRACTION` / `ENABLE_STREAMING`.

## 🗺️ Roadmap

- [ ] Streaming TTS + streaming ASR (interfaces already reserved in `tts_service`)
- [ ] Voice activity detection & barge-in interrupt for call mode
- [ ] Vector embeddings / hybrid memory retrieval (retriever interface stable)
- [ ] Multi-persona support (`user_states.current_persona_id` already in schema)
- [ ] Mobile app shell (REST + SocketIO API is client-agnostic)

## License

MIT (personal/demo project — bring your own API keys and voice models).
