import os


def _require(name: str) -> str:
    val = os.getenv(name)
    if not val:
        raise RuntimeError(
            f"Variavel de ambiente {name} é obrigatória. "
            "Defina-a no .env ou no ambiente do container."
        )
    return val


ALLOWED_ORIGINS = _require("ALLOWED_ORIGINS").split(",")

DB_PATH = os.getenv("DB_PATH", "/data/forms.db")

ADMIN_KEY = _require("ADMIN_KEY")

TOKEN_TTL_HOURS = int(os.getenv("TOKEN_TTL_HOURS", "48"))

SERVICOS_VALIDOS = {"suporte", "seguranca", "desenvolvimento"}

SMTP_HOST = os.getenv("SMTP_HOST")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASS = os.getenv("SMTP_PASS")
SMTP_FROM = os.getenv("SMTP_FROM", SMTP_USER)
NOTIFY_TO = os.getenv("NOTIFY_TO")
PAINEL_BASE_URL = _require("PAINEL_BASE_URL")

RATE_LIMIT = int(os.getenv("RATE_LIMIT", "10"))
RATE_LIMIT_WINDOW = 60
