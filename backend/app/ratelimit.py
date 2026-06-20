import time
from collections import defaultdict

from fastapi import HTTPException, Request

from app.config import RATE_LIMIT, RATE_LIMIT_WINDOW


_window: dict[str, list[float]] = defaultdict(list)


def check_rate_limit(request: Request):
    key = f"{request.client.host}:{request.url.path}"
    now = time.time()
    cutoff = now - RATE_LIMIT_WINDOW

    timestamps = _window[key]
    timestamps[:] = [t for t in timestamps if t > cutoff]

    if len(timestamps) >= RATE_LIMIT:
        raise HTTPException(status_code=429, detail="Muitas requisições. Aguarde e tente novamente.")

    timestamps.append(now)
