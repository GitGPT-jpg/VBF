"""Audio asset persistence."""
from __future__ import annotations

from typing import Any

from app.models.schemas import AudioAsset, _meta_dumps, _meta_loads
from app.repositories.db import get_conn
from app.utils.ids import new_id
from app.utils.time import now_iso


def _row_to_asset(row) -> AudioAsset:
    return AudioAsset(
        id=row["id"], user_id=row["user_id"], message_id=row["message_id"],
        asset_type=row["asset_type"], file_path=row["file_path"],
        public_url=row["public_url"], duration_ms=row["duration_ms"],
        provider=row["provider"], metadata=_meta_loads(row["metadata_json"]),
        created_at=row["created_at"],
    )


def create(user_id: str, asset_type: str, file_path: str, public_url: str = "",
           message_id: str = "", duration_ms: int = 0, provider: str = "",
           metadata: dict[str, Any] | None = None) -> AudioAsset:
    asset = AudioAsset(
        id=new_id("aud"), user_id=user_id, message_id=message_id,
        asset_type=asset_type, file_path=file_path, public_url=public_url,
        duration_ms=duration_ms, provider=provider, metadata=metadata or {},
        created_at=now_iso())
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO audio_assets (id, user_id, message_id, asset_type,"
            " file_path, public_url, duration_ms, provider, metadata_json, created_at)"
            " VALUES (?,?,?,?,?,?,?,?,?,?)",
            (asset.id, asset.user_id, asset.message_id, asset.asset_type,
             asset.file_path, asset.public_url, asset.duration_ms, asset.provider,
             _meta_dumps(asset.metadata), asset.created_at))
    return asset


def get(asset_id: str) -> AudioAsset | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM audio_assets WHERE id = ?", (asset_id,)).fetchone()
    return _row_to_asset(row) if row else None


def list_for_user(user_id: str, limit: int = 200) -> list[AudioAsset]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM audio_assets WHERE user_id = ?"
            " ORDER BY created_at DESC LIMIT ?", (user_id, limit)).fetchall()
    return [_row_to_asset(r) for r in rows]
