import secrets
import string
from datetime import datetime

from fastapi import HTTPException

from app.config import ADMIN_KEY
from app.database import get_db


def gerar_token() -> str:
    return secrets.token_urlsafe(24)


def gerar_codigo_consulta() -> str:
    alphabet = string.ascii_uppercase + string.digits
    parte = lambda: "".join(secrets.choice(alphabet) for _ in range(4))
    return f"NLC-{parte()}-{parte()}"


def checar_admin(x_admin_key: str | None):
    if not x_admin_key or x_admin_key != ADMIN_KEY:
        raise HTTPException(status_code=401, detail="Chave de admin inválida.")


def validar_e_consumir_token(token: str, servico: str) -> None:
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT * FROM tokens WHERE token = ?", (token,)
        ).fetchone()

        if row is None:
            raise HTTPException(status_code=403, detail="Token inválido.")

        if row["servico"] != servico:
            raise HTTPException(status_code=403, detail="Token não corresponde a este formulário.")

        if row["usado"]:
            raise HTTPException(status_code=403, detail="Este link já foi utilizado.")

        expira_em = datetime.fromisoformat(row["expira_em"])
        if datetime.utcnow() > expira_em:
            raise HTTPException(status_code=403, detail="Este link expirou.")

        conn.execute(
            "UPDATE tokens SET usado = 1, usado_em = ? WHERE token = ?",
            (datetime.utcnow().isoformat(), token),
        )
        conn.commit()
    finally:
        conn.close()
