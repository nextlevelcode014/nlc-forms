from typing import Annotated

from pydantic import ValidationError, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


SERVICOS_VALIDOS = {"suporte", "seguranca", "desenvolvimento"}

# Nome do serviço como o cliente lê. Mesmos rótulos do ROTULO_SERVICO em
# frontend/shared/lib/triagem.ts — quando um lado muda, o outro precisa mudar
# junto. (O notify.py ainda carrega três cópias deste mapa; migrar para cá é
# limpeza pendente, não parte desta mudança.)
ROTULO_SERVICO = {
    "suporte": "Suporte Técnico",
    "seguranca": "Segurança & Privacidade",
    "desenvolvimento": "Dev & Automação",
}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Obrigatórias ──
    allowed_origins: Annotated[list[str], NoDecode]
    admin_key: str
    painel_base_url: str

    # ── Banco ──
    db_path: str = "/data/forms.db"

    # ── Tokens ──
    token_ttl_hours: int = 48

    # ── SMTP (opcional — sem host, e-mails são ignorados) ──
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_pass: str = ""
    smtp_from: str = ""
    notify_to: str = ""

    # ── Rate limit ──
    rate_limit: int = 10
    rate_limit_window: int = 60

    # ── Popular o banco com clientes fictícios (só para demo/testes) ──
    seed_demo: bool = False

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def _split_origins(cls, v):
        """ALLOWED_ORIGINS vem como lista separada por vírgula, não como JSON."""
        if isinstance(v, str):
            return [o.strip() for o in v.split(",") if o.strip()]
        return v

    @model_validator(mode="after")
    def _smtp_from_default(self):
        if not self.smtp_from:
            self.smtp_from = self.smtp_user
        return self


def _carregar() -> Settings:
    try:
        return Settings()
    except ValidationError as e:
        faltando = [
            str(erro["loc"][0]).upper()
            for erro in e.errors()
            if erro["type"] == "missing"
        ]
        if faltando:
            raise RuntimeError(
                f"Variáveis de ambiente obrigatórias não definidas: {', '.join(faltando)}. "
                "Defina-as no .env ou no ambiente do container (veja .env.example)."
            ) from e
        raise


settings = _carregar()
