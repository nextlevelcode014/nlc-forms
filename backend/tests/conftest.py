"""Ambiente dos testes.

O conftest.py é importado pelo pytest antes dos módulos de teste, e é o único
lugar onde dá para definir as variáveis *antes* de `app.config` ser importado —
o Settings é instanciado no import, então depois disso já seria tarde.

Variáveis de ambiente têm precedência sobre o arquivo .env no pydantic-settings.
Isso é o que garante que rodar os testes com um .env real na pasta não vá usar
o banco de produção: o DB_PATH abaixo vence.
"""

import os
import tempfile

os.environ["DB_PATH"] = os.path.join(tempfile.mkdtemp(prefix="nlc-test-"), "forms.db")
os.environ["ADMIN_KEY"] = "test-admin-key"
os.environ["ALLOWED_ORIGINS"] = "http://localhost:9080"
os.environ["PAINEL_BASE_URL"] = "http://localhost:9080"
os.environ["SMTP_HOST"] = ""
os.environ["SEED_DEMO"] = "false"

import pytest  # noqa: E402

from app.database import init_db, get_db  # noqa: E402
from app.ratelimit import _window  # noqa: E402


@pytest.fixture(autouse=True)
def setup_db():
    """Banco limpo e rate limiter zerado antes de cada teste.

    O _window é global ao processo, então sem essa limpeza os testes somam
    requisições entre si e, passando de RATE_LIMIT, começam a receber 429 —
    falha que aparece só quando a suíte cresce.
    """
    _window.clear()
    init_db()
    conn = get_db()
    for tabela in (
        "historico",
        "clientes",
        "tokens",
        "triagem_suporte",
        "triagem_seguranca",
        "triagem_desenvolvimento",
        "execucao",
        "relatorios_md",
    ):
        conn.execute(f"DELETE FROM {tabela}")
    conn.commit()
    conn.close()
    yield
