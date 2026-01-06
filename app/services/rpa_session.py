import logging
import os
import time

from redis import Redis

logger = logging.getLogger(__name__)

STATUS_KEY = "rpa:session_status"
STATUS_TTL_SECONDS = 3600


def _get_redis():
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    return Redis.from_url(
        redis_url,
        socket_connect_timeout=3,
        socket_timeout=3,
        retry_on_timeout=False,
    )


def set_status(state: str, active_until: float | None = None, cooldown_until: float | None = None) -> None:
    try:
        redis = _get_redis()
        now = int(time.time())
        payload = {
            "state": state,
            "updated_at": now,
        }
        if active_until is not None:
            payload["active_until"] = int(active_until)
        if cooldown_until is not None:
            payload["cooldown_until"] = int(cooldown_until)
        redis.hset(STATUS_KEY, mapping=payload)
        redis.expire(STATUS_KEY, STATUS_TTL_SECONDS)
    except Exception:
        logger.exception("RPA: no se pudo guardar el estado de sesion")


def get_status() -> dict:
    try:
        redis = _get_redis()
        data = redis.hgetall(STATUS_KEY)
        if not data:
            return {"state": "none"}
        result = {
            "state": data.get(b"state", b"none").decode("utf-8", "ignore"),
        }
        for field in ("active_until", "cooldown_until", "updated_at"):
            if field.encode() in data:
                try:
                    result[field] = int(data[field.encode()])
                except Exception:
                    pass
        return result
    except Exception:
        logger.exception("RPA: no se pudo leer el estado de sesion")
        return {"state": "unknown"}


def mark_running() -> None:
    set_status("running")


def mark_active(seconds: int) -> None:
    set_status("active", active_until=time.time() + seconds)


def mark_cooldown(seconds: int) -> None:
    if seconds <= 0:
        set_status("none")
    else:
        set_status("cooldown", cooldown_until=time.time() + seconds)
