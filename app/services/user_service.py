"""UserService — registration, authentication, bootstrap migration."""
from __future__ import annotations

from werkzeug.security import check_password_hash, generate_password_hash

from app.config.settings import settings
from app.models.schemas import User, UserState
from app.repositories import user_repository as user_repo
from app.utils.logger import get_logger
from app.utils.security import LoginThrottle

log = get_logger(__name__)

login_throttle = LoginThrottle(max_attempts=5, window_sec=300)


def ensure_bootstrap_users() -> None:
    """Migrate the two legacy .env accounts into the users table (first run)."""
    for username, password, role in (
            (settings.bootstrap_owner_user, settings.bootstrap_owner_pass, "owner"),
            (settings.bootstrap_companion_user, settings.bootstrap_companion_pass, "user")):
        if not username:
            continue
        if user_repo.get_by_username(username) is None:
            user_repo.create_user(username, generate_password_hash(password), role=role)
            log.info("Bootstrapped user %r (role=%s)", username, role)


def authenticate(username: str, password: str, remote_addr: str = "") -> User | None:
    """Verify credentials with login throttling. Returns User or None."""
    throttle_key = f"{username}|{remote_addr}"
    if login_throttle.is_blocked(throttle_key):
        log.warning("Login throttled for %r", username)
        return None
    user = user_repo.get_by_username(username)
    if user and check_password_hash(user.password_hash, password):
        login_throttle.reset(throttle_key)
        user_repo.touch_last_login(user.id)
        return user
    login_throttle.record_failure(throttle_key)
    return None


def get_user(user_id: str) -> User | None:
    return user_repo.get_by_id(user_id)


def get_state(user_id: str) -> UserState:
    return user_repo.get_state(user_id)


def save_state(state: UserState) -> None:
    user_repo.save_state(state)
