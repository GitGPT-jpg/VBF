"""SingingService — productized RVC singing pipeline with cancellable tasks."""
from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any, Callable

from app.config.settings import settings
from app.utils.ids import new_id
from app.utils.logger import get_logger

log = get_logger(__name__)

# Task statuses: matching / generating / ready / cancelled / failed
@dataclass
class SingingTask:
    task_id: str
    user_id: str
    song: dict[str, Any]
    status: str = "matching"
    file_path: str = ""
    error: str = ""
    _cancel_event: threading.Event = field(default_factory=threading.Event)

    @property
    def cancelled(self) -> bool:
        return self._cancel_event.is_set()


_tasks: dict[str, SingingTask] = {}
_tasks_lock = threading.Lock()


def list_songs() -> list[dict[str, Any]]:
    from sing import list_songs as legacy_list
    try:
        return legacy_list()
    except Exception as exc:  # noqa: BLE001
        log.warning("list_songs failed: %s", exc)
        return []


def match_song(query: str) -> dict[str, Any] | None:
    from sing import match_song as legacy_match
    try:
        return legacy_match(query) if query else None
    except Exception as exc:  # noqa: BLE001
        log.warning("match_song failed: %s", exc)
        return None


def get_random_song() -> dict[str, Any] | None:
    from sing import get_random_song as legacy_random
    try:
        return legacy_random()
    except Exception as exc:  # noqa: BLE001
        log.warning("get_random_song failed: %s", exc)
        return None


def start_singing_task(user_id: str, song: dict[str, Any],
                       on_done: Callable[[SingingTask], None] | None = None) -> SingingTask:
    """Run the RVC pipeline in a background thread; returns the task handle."""
    if not settings.enable_singing:
        task = SingingTask(task_id=new_id("sing"), user_id=user_id, song=song,
                           status="failed", error="singing disabled")
        return task

    task = SingingTask(task_id=new_id("sing"), user_id=user_id, song=song,
                       status="generating")
    with _tasks_lock:
        _tasks[task.task_id] = task

    def worker() -> None:
        try:
            from sing import sing as legacy_sing
            wav = legacy_sing(task.song)
            if task.cancelled:
                task.status = "cancelled"
                return
            if wav:
                task.file_path = wav
                task.status = "ready"
            else:
                task.status = "failed"
                task.error = "render returned empty result"
        except Exception as exc:  # noqa: BLE001
            log.error("singing task %s failed: %s", task.task_id, exc)
            task.status = "failed"
            task.error = str(exc)
        finally:
            if on_done and not task.cancelled:
                try:
                    on_done(task)
                except Exception as exc:  # noqa: BLE001
                    log.warning("singing on_done callback failed: %s", exc)

    threading.Thread(target=worker, daemon=True).start()
    return task


def cancel_singing_task(task_id: str, user_id: str) -> bool:
    with _tasks_lock:
        task = _tasks.get(task_id)
    if not task or task.user_id != user_id:
        return False
    task._cancel_event.set()
    task.status = "cancelled"
    return True


def get_singing_status(task_id: str) -> dict[str, Any] | None:
    with _tasks_lock:
        task = _tasks.get(task_id)
    if not task:
        return None
    return {"task_id": task.task_id, "status": task.status,
            "title": task.song.get("title", ""), "error": task.error}
