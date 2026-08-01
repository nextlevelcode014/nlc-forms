import secrets
import string

from fastapi import HTTPException

from app.config import settings
from app.tempo import agora, agora_iso, parse as parse_data


def gerar_token() -> str:
    return secrets.token_urlsafe(24)


def gerar_codigo_consulta() -> str:
    alphabet = string.ascii_uppercase + string.digits
    parte = lambda: "".join(secrets.choice(alphabet) for _ in range(4))
    return f"NLC-{parte()}-{parte()}"


def checar_admin(x_admin_key: str | None):
    # compare_digest em vez de != : comparação de tempo constante, para a chave
    # não vazar caractere a caractere por timing. .encode() evita TypeError
    # se a chave tiver acento.
    if not x_admin_key or not secrets.compare_digest(
        x_admin_key.encode(), settings.admin_key.encode()
    ):
        raise HTTPException(status_code=401, detail="Chave de admin inválida.")


def validar_token(conn, token: str, servico: str) -> None:
    """Recusa o token se não existir, for de outro serviço, já tiver sido usado
    ou tiver expirado. Não marca nada — quem consome é `consumir_token`."""
    row = conn.execute("SELECT * FROM tokens WHERE token = ?", (token,)).fetchone()

    if row is None:
        raise HTTPException(status_code=403, detail="Token inválido.")

    if row["servico"] != servico:
        raise HTTPException(
            status_code=403, detail="Token não corresponde a este formulário."
        )

    if row["usado"]:
        raise HTTPException(status_code=403, detail="Este link já foi utilizado.")

    if agora() > parse_data(row["expira_em"]):
        raise HTTPException(status_code=403, detail="Este link expirou.")


def consumir_token(conn, token: str) -> None:
    """Marca o token como usado.

    O `AND usado = 0` deixa o UPDATE condicional: se duas requisições passarem
    pela validação ao mesmo tempo, só a primeira altera uma linha e a segunda
    é recusada, em vez de as duas gravarem a triagem.
    """
    cur = conn.execute(
        "UPDATE tokens SET usado = 1, usado_em = ? WHERE token = ? AND usado = 0",
        (agora_iso(), token),
    )
    if cur.rowcount == 0:
        raise HTTPException(status_code=403, detail="Este link já foi utilizado.")
