"""Auth logic tests — hashing, throttling, bootstrap."""
from werkzeug.security import generate_password_hash

from app.repositories import user_repository as user_repo
from app.services import user_service
from app.utils.security import LoginThrottle


def test_authenticate_success(temp_db):
    user_repo.create_user("alice", generate_password_hash("s3cret"))
    user = user_service.authenticate("alice", "s3cret", remote_addr="1.1.1.1")
    assert user is not None
    assert user.username == "alice"
    assert user_repo.get_by_id(user.id).last_login_at != ""


def test_authenticate_wrong_password(temp_db):
    user_repo.create_user("alice", generate_password_hash("s3cret"))
    assert user_service.authenticate("alice", "wrong", remote_addr="1.1.1.1") is None


def test_authenticate_unknown_user(temp_db):
    assert user_service.authenticate("ghost", "x", remote_addr="1.1.1.1") is None


def test_login_throttle_blocks_after_failures():
    throttle = LoginThrottle(max_attempts=3, window_sec=60)
    for _ in range(3):
        throttle.record_failure("k")
    assert throttle.is_blocked("k") is True
    throttle.reset("k")
    assert throttle.is_blocked("k") is False


def test_throttled_login_rejected(temp_db):
    user_repo.create_user("alice", generate_password_hash("s3cret"))
    key_addr = "9.9.9.9"
    for _ in range(5):
        user_service.authenticate("alice", "wrong", remote_addr=key_addr)
    # correct password while throttled is still rejected
    assert user_service.authenticate("alice", "s3cret", remote_addr=key_addr) is None


def test_bootstrap_users_idempotent(temp_db):
    user_service.ensure_bootstrap_users()
    count_first = len(user_repo.list_users())
    user_service.ensure_bootstrap_users()
    assert len(user_repo.list_users()) == count_first
    assert count_first >= 1
