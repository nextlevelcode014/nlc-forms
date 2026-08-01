import time

from fastapi import HTTPException, Request

from app.config import settings


_window: dict[str, list[float]] = {}


def _ip_cliente(request: Request) -> str:
    """IP real do cliente.

    Atrás do Tailscale Funnel toda requisição chega do proxy, então
    request.client.host seria o mesmo para todo mundo e um cliente sozinho
    derrubaria o limite de todos. O uvicorn roda com --proxy-headers, que já
    reescreve request.client a partir do X-Forwarded-For; o fallback abaixo
    cobre o caso de ele estar desligado.
    """
    encaminhado = request.headers.get("x-forwarded-for")
    if encaminhado:
        return encaminhado.split(",")[0].strip()
    return request.client.host if request.client else "desconhecido"


def check_rate_limit(request: Request):
    key = f"{_ip_cliente(request)}:{request.url.path}"
    now = time.time()
    cutoff = now - settings.rate_limit_window

    timestamps = [t for t in _window.get(key, []) if t > cutoff]

    if len(timestamps) >= settings.rate_limit:
        _window[key] = timestamps
        raise HTTPException(
            status_code=429, detail="Muitas requisições. Aguarde e tente novamente."
        )

    timestamps.append(now)
    _window[key] = timestamps
    _limpar_expirados(cutoff)


def _limpar_expirados(cutoff: float) -> None:
    """Remove chaves sem timestamps vivos — senão o dict cresce para sempre."""
    if len(_window) < 512:
        return
    for k in [k for k, v in _window.items() if not v or v[-1] <= cutoff]:
        del _window[k]
