import os

ALLOWED_ORIGINS = os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost:5500,http://127.0.0.1:5500,http://localhost:3000,"
    "http://localhost:9080,http://127.0.0.1:9080,http://localhost:8080,http://127.0.0.1:8080"
).split(",")

DB_PATH = os.getenv("DB_PATH", "/data/forms.db")

ADMIN_KEY = os.getenv("ADMIN_KEY", "troque-essa-chave")

TOKEN_TTL_HOURS = int(os.getenv("TOKEN_TTL_HOURS", "48"))

SERVICOS_VALIDOS = {"suporte", "seguranca", "desenvolvimento"}

SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")
SMTP_FROM = os.getenv("SMTP_FROM", SMTP_USER)
NOTIFY_TO = os.getenv("NOTIFY_TO", "")
PAINEL_BASE_URL = os.getenv("PAINEL_BASE_URL", "http://localhost:9080")

RATE_LIMIT = int(os.getenv("RATE_LIMIT", "10"))
RATE_LIMIT_WINDOW = 60
