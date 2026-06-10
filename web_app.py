"""Web 入口 — AI Companion Chat App

兼容旧启动方式：
    1. python web_app.py
    2. ngrok http 5000
    3. 把 ngrok 给的 https:// 链接分享出去

实际应用代码位于 app/ 包（架构见 README）。
"""
from app.main import run

if __name__ == "__main__":
    run()
