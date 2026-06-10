"""AI Companion Chat App — application package.

Layered architecture:
    api/          HTTP blueprints (auth, chat, audio, admin)
    websocket/    SocketIO event handlers (chat, call, sing, presence)
    services/     Business logic (chat orchestration, llm, tts, memory, ...)
    agents/       AI-native components (intent router, prompt builder, state machine)
    repositories/ SQLite persistence (no SQL in business layer)
    models/       Typed schemas (dataclasses)
    config/       Environment-driven settings
    utils/        Logging, security, ids, time helpers
"""
