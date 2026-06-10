"""Repository CRUD tests against an isolated temp database."""
from app.repositories import (
    audio_repository as audio_repo,
    conversation_repository as conv_repo,
    memory_repository as memory_repo,
    message_repository as msg_repo,
    user_repository as user_repo,
)


def _user(username="alice"):
    return user_repo.create_user(username, "hash", role="user")


def test_user_crud(temp_db):
    user = _user()
    assert user_repo.get_by_username("alice").id == user.id
    assert user_repo.get_by_id(user.id).username == "alice"
    user_repo.touch_last_login(user.id)
    assert user_repo.get_by_id(user.id).last_login_at != ""


def test_user_state_roundtrip(temp_db):
    user = _user()
    state = user_repo.get_state(user.id)
    assert state.dialog_state == "idle"
    state.dialog_state = "sleep_mode"
    state.sleep_mode_enabled = True
    user_repo.save_state(state)
    loaded = user_repo.get_state(user.id)
    assert loaded.dialog_state == "sleep_mode"
    assert loaded.sleep_mode_enabled is True


def test_conversation_lifecycle(temp_db):
    user = _user()
    conv = conv_repo.create(user.id, title="测试")
    assert conv_repo.get(conv.id).title == "测试"
    assert len(conv_repo.list_for_user(user.id)) == 1
    conv_repo.set_archived(conv.id, True)
    assert conv_repo.list_for_user(user.id) == []
    assert len(conv_repo.list_for_user(user.id, include_archived=True)) == 1
    conv_repo.delete(conv.id)
    assert conv_repo.get(conv.id) is None


def test_message_crud_and_history(temp_db):
    user = _user()
    conv = conv_repo.create(user.id)
    msg_repo.create(conv.id, user.id, "user", "你好", intent="chat")
    msg_repo.create(conv.id, user.id, "assistant", "嗯，我在呢", intent="chat")
    history = msg_repo.list_for_conversation(conv.id)
    assert [m.role for m in history] == ["user", "assistant"]
    turns = msg_repo.recent_turns(conv.id)
    assert turns[0] == {"role": "user", "content": "你好"}


def test_message_delete_ownership(temp_db):
    alice, bob = _user("alice"), _user("bob")
    conv = conv_repo.create(alice.id)
    msg = msg_repo.create(conv.id, alice.id, "user", "私密内容")
    assert msg_repo.delete(msg.id, bob.id) is False  # not the owner
    assert msg_repo.delete(msg.id, alice.id) is True


def test_memory_crud(temp_db):
    user = _user()
    mem = memory_repo.create(user.id, "preference", "喜欢小狗", importance=4)
    assert memory_repo.get(mem.id).content == "喜欢小狗"
    assert memory_repo.find_duplicate(user.id, "preference", "喜欢小狗") is not None
    memory_repo.update(mem.id, user.id, importance=5)
    assert memory_repo.get(mem.id).importance == 5
    memory_repo.soft_delete(mem.id, user.id)
    assert memory_repo.list_for_user(user.id) == []
    assert memory_repo.get(mem.id) is not None  # soft delete keeps row


def test_memory_clear(temp_db):
    user = _user()
    memory_repo.create(user.id, "episodic", "a")
    memory_repo.create(user.id, "episodic", "b")
    assert memory_repo.clear_for_user(user.id) == 2
    assert memory_repo.list_for_user(user.id) == []


def test_audio_asset_crud(temp_db):
    user = _user()
    asset = audio_repo.create(user.id, "tts", "tts_cache/x.mp3",
                              public_url="/audio/tts/x.mp3", provider="edge")
    loaded = audio_repo.get(asset.id)
    assert loaded.public_url == "/audio/tts/x.mp3"
    assert audio_repo.list_for_user(user.id)[0].id == asset.id
