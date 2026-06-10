"""Audio routes — authenticated, traversal-safe file serving."""
from __future__ import annotations

import os

from flask import Blueprint, abort, send_from_directory
from flask_login import login_required

from config import SING_OUTPUT_DIR, TTS_OUTPUT_DIR
from app.utils.security import safe_join

bp = Blueprint("audio", __name__)


def _serve(base_dir: str, filename: str):
    base = os.path.abspath(base_dir)
    path = safe_join(base, filename)
    if path is None or not os.path.exists(path):
        abort(404 if path else 403)
    return send_from_directory(base, filename)


@bp.route("/audio/tts/<path:filename>")
@login_required
def audio_tts(filename: str):
    return _serve(TTS_OUTPUT_DIR, filename)


@bp.route("/audio/sing/<path:filename>")
@login_required
def audio_sing(filename: str):
    return _serve(SING_OUTPUT_DIR, filename)
