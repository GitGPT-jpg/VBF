"""Chat REST API — conversations, messages, memories, data export.

All endpoints enforce per-user data isolation: a user can only touch their own
conversations, messages and memories.
"""
from __future__ import annotations

from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required

from app.services import conversation_service, memory_service, message_service

bp = Blueprint("chat_api", __name__, url_prefix="/api")


# ── conversations ────────────────────────────────────────────────────────────

@bp.get("/conversations")
@login_required
def list_conversations():
    include_archived = request.args.get("archived") == "1"
    convs = conversation_service.list_for_user(
        current_user.id, include_archived=include_archived)
    return jsonify([{
        "id": c.id, "title": c.title, "mode": c.mode, "archived": c.archived,
        "created_at": c.created_at, "last_message_at": c.last_message_at,
    } for c in convs])


@bp.post("/conversations")
@login_required
def create_conversation():
    data = request.get_json(silent=True) or {}
    conv = conversation_service.create(current_user.id,
                                       title=(data.get("title") or "").strip())
    return jsonify({"id": conv.id, "title": conv.title}), 201


@bp.get("/conversations/active")
@login_required
def active_conversation():
    conv = conversation_service.get_or_create(current_user.id)
    msgs = message_service.history(conv.id, limit=100)
    return jsonify({
        "id": conv.id, "title": conv.title,
        "messages": [message_service.serialize(m) for m in msgs],
    })


@bp.get("/conversations/<conv_id>/messages")
@login_required
def conversation_messages(conv_id: str):
    conv = conversation_service.get_or_create(current_user.id, conv_id)
    if conv.id != conv_id:
        return jsonify({"error": "not found"}), 404
    before = request.args.get("before", "")
    msgs = message_service.history(conv.id, limit=100, before=before)
    return jsonify([message_service.serialize(m) for m in msgs])


@bp.post("/conversations/<conv_id>/archive")
@login_required
def archive_conversation(conv_id: str):
    ok = conversation_service.archive(conv_id, current_user.id)
    return (jsonify({"ok": True}), 200) if ok else (jsonify({"error": "not found"}), 404)


@bp.delete("/conversations/<conv_id>")
@login_required
def delete_conversation(conv_id: str):
    ok = conversation_service.delete(conv_id, current_user.id)
    return (jsonify({"ok": True}), 200) if ok else (jsonify({"error": "not found"}), 404)


# ── messages ─────────────────────────────────────────────────────────────────

@bp.post("/messages/<message_id>/favorite")
@login_required
def favorite_message(message_id: str):
    ok = message_service.toggle_favorite(message_id, current_user.id)
    return (jsonify({"ok": True}), 200) if ok else (jsonify({"error": "not found"}), 404)


@bp.delete("/messages/<message_id>")
@login_required
def delete_message(message_id: str):
    ok = message_service.delete(message_id, current_user.id)
    return (jsonify({"ok": True}), 200) if ok else (jsonify({"error": "not found"}), 404)


# ── memories ─────────────────────────────────────────────────────────────────

@bp.get("/memories")
@login_required
def list_memories():
    memory_type = request.args.get("type", "")
    return jsonify([m.to_dict() for m in
                    memory_service.list_memories(current_user.id, memory_type)])


@bp.delete("/memories/<memory_id>")
@login_required
def delete_memory(memory_id: str):
    ok = memory_service.delete_memory(memory_id, current_user.id)
    return (jsonify({"ok": True}), 200) if ok else (jsonify({"error": "not found"}), 404)


@bp.delete("/memories")
@login_required
def clear_memories():
    count = memory_service.clear_memories(current_user.id)
    return jsonify({"ok": True, "cleared": count})


# ── user data control ────────────────────────────────────────────────────────

@bp.get("/export")
@login_required
def export_my_data():
    """Export the requesting user's conversations, messages and memories."""
    convs = conversation_service.list_for_user(current_user.id, include_archived=True)
    payload = {
        "user": {"id": current_user.id, "username": current_user.username},
        "conversations": [],
        "memories": memory_service.export_memories(current_user.id),
    }
    for conv in convs:
        payload["conversations"].append({
            "id": conv.id, "title": conv.title, "created_at": conv.created_at,
            "messages": [message_service.serialize(m)
                         for m in message_service.history(conv.id, limit=1000)],
        })
    return jsonify(payload)
