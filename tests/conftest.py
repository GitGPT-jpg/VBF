"""Shared pytest fixtures — isolated temp database per test."""
from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import settings as settings_module  # noqa: E402
from app.repositories import db as db_module  # noqa: E402


@pytest.fixture()
def temp_db(tmp_path, monkeypatch):
    """Point the app at a fresh SQLite file for each test."""
    db_path = str(tmp_path / "test.db")
    monkeypatch.setattr(db_module, "_db_path", lambda: db_path)
    db_module.reset_init_cache()
    db_module.init_db(db_path)
    yield db_path
    db_module.reset_init_cache()
