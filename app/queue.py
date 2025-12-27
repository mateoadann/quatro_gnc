from redis import Redis
from rq import Queue

from flask import current_app


def get_queue(for_worker: bool = False) -> Queue:
    redis_url = current_app.config.get("REDIS_URL")
    timeout = current_app.config.get("RQ_DEFAULT_TIMEOUT", 900)

    if for_worker:
        redis = Redis.from_url(
            redis_url,
            socket_connect_timeout=5,
            socket_timeout=None,
            retry_on_timeout=True,
        )
    else:
        redis = Redis.from_url(
            redis_url,
            socket_connect_timeout=3,
            socket_timeout=3,
            retry_on_timeout=False,
        )

    return Queue(connection=redis, default_timeout=timeout, is_async=True)
