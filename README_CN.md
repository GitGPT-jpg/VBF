# Voice Companion Agent — AI 原生陪伴聊天应用

> **一个 AI 原生陪伴聊天 App MVP**：人格化对话、长期记忆、流式回复、语音陪伴、AI 唱歌、情绪感知状态机 —— 基于 Flask + SocketIO + Claude。

[English README](README.md)

## ✨ 功能一览

- 💬 **聊天软件级体验** — 消息气泡、逐字流式输出、刷新不丢历史、会话管理（新建 / 归档 / 删除）
- 🧠 **长期记忆系统** — LLM 结构化提取 6 类记忆（`profile / preference / episodic / emotional / relationship / task`），带重要度与置信度评分、去重、召回，用户可删除/清空
- 🗣️ **语音陪伴** — 每条回复生成 TTS 音频资产（edge-tts → 可选 RVC 音色转换），逐条可重播
- 📞 **通话模式** — 电话式 UI、极速短回复、语音识别输入、挂断关键词
- 🎵 **AI 唱歌** — 可取消的云端 RVC 唱歌任务（Replicate），歌曲匹配 + 状态跟踪
- 😴 **睡眠模式** — 极短、缓慢、不提问的哄睡回复
- 🎭 **情绪感知** — 规则情绪分析自动切换安慰模式；对话状态机驱动前端动效

## 🏗️ 技术架构

```
voice-companion-agent/
├── web_app.py                 # 启动入口：python web_app.py
├── app/
│   ├── main.py                # 应用工厂（Flask + SocketIO 装配）
│   ├── api/                   # REST 蓝图：auth / chat / audio / admin
│   ├── websocket/             # SocketIO 事件：chat（流式）/ call / sing / presence
│   ├── services/              # 业务逻辑
│   │   ├── chat_service.py    #   ← 编排器（单轮对话完整管线）
│   │   ├── llm_service.py     #   Claude 封装：complete / stream / classify_json
│   │   ├── memory_service.py  #   LLM 结构化记忆提取 + 生命周期
│   │   ├── tts_service.py     #   统一 TTS + 音频资产记账
│   │   ├── singing_service.py #   异步可取消唱歌任务
│   │   └── ...                #   user / conversation / message / safety
│   ├── agents/                # AI 原生组件
│   │   ├── intent_router.py   #   14 种意图：规则 → LLM JSON → 缓存 → 兜底
│   │   ├── prompt_builder.py  #   5 层 Prompt：人格/用户/会话/记忆/策略
│   │   ├── dialog_state_machine.py  # 10 状态 × 16 事件
│   │   ├── memory_retriever.py      # 相似度 + 重要度 + 时效评分
│   │   ├── emotion_analyzer.py
│   │   └── response_policy.py       # 按模式的回复参数
│   ├── repositories/          # SQLite 持久化（业务层不写 SQL）
│   ├── models/schemas.py      # 类型化 dataclass
│   ├── config/settings.py     # 环境变量配置 + 生产环境安全检查
│   └── utils/                 # 日志（密钥脱敏）/ 安全 / id / 时间
├── templates/  static/        # 移动端优先 Web UI
├── tests/                     # pytest 测试套件（44 个用例）
└── migrations/                # 旧数据导入
```

**单轮对话管线**（`chat_service.run_chat_turn`）：

```
用户输入 ──► 意图路由 ──► 情绪分析 ──► 持久化用户消息
        ──► PromptBuilder（人格 + 记忆 + 策略）
        ──► Claude 流式 ──► assistant_message_start/delta/done 事件
        ──► 持久化 AI 消息 ──► TTS 音频资产
        ──► 异步记忆提取 ──► 更新 user_states
```

## 🗃️ 数据模型（SQLite）

| 表 | 用途 |
|---|---|
| `users` | 哈希密码、角色、显示名 |
| `conversations` | 用户会话：模式 / 归档标记 |
| `messages` | 每条消息持久化：role、content_type（text/voice/song/card）、intent、state、metadata |
| `memories` | 6 类长期记忆：importance(1-5)、confidence(0-1)、软删除 |
| `audio_assets` | 每段音频：类型、路径、URL、provider |
| `user_states` | 对话状态、情绪状态、睡眠/通话模式 |

轻量版本化迁移见 `app/repositories/db.py`；旧 `logs/conversations.db` 可用 `python migrations/import_legacy_logs.py` 导入。

## 🚀 快速开始

```bash
git clone https://github.com/GitGPT-jpg/voice-companion-agent.git
cd voice-companion-agent
pip install -r requirements.txt
cp .env.example .env        # 填入 ANTHROPIC_API_KEY 等
python web_app.py           # → http://127.0.0.1:5000/login
```

本地演示如果使用 Chromium 浏览器，避免使用 `5060` 和 `5061`，因为它们会被判定为不安全端口（`ERR_UNSAFE_PORT`）。可改用：

```bash
WEB_PORT=5500 python web_app.py
```

运行测试：

```bash
pytest
```

## 🔐 安全与隐私

- 生产环境启动检查：`APP_ENV=production` 时拒绝弱密钥与 `admin/admin` 默认账号
- 密码哈希入库、登录限流（5 次 / 5 分钟）、HttpOnly + SameSite Cookie
- 用户数据隔离（消息 / 记忆 / 音频）；音频路径防穿越
- 日志密钥脱敏；数据导出（`GET /api/export`）、删除对话、清空记忆

## ⚙️ 环境变量

见 [.env.example](.env.example)，核心项：`APP_ENV`、`WEB_SECRET_KEY`、`ANTHROPIC_API_KEY`、`ANTHROPIC_MODEL`、`TTS_PROVIDER`、`REPLICATE_API_KEY`，以及功能开关 `ENABLE_SINGING` / `ENABLE_MEMORY_EXTRACTION` / `ENABLE_STREAMING`。

## 🗺️ Roadmap

- [ ] 流式 TTS + 流式 ASR（`tts_service` 已预留接口）
- [ ] 通话模式 VAD 与打断（barge-in）
- [ ] 向量化 / 混合记忆检索（检索器接口已稳定）
- [ ] 多人格支持（schema 已含 `current_persona_id`）
- [ ] 移动端 App 外壳（REST + SocketIO API 与客户端解耦）

## License

MIT（个人/演示项目 —— 请自备 API Key 与音色模型）。
