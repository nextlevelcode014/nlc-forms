from fastapi import APIRouter, Depends, Query

from app.database import get_db
from app.ratelimit import check_rate_limit
from app.tempo import agora, parse as parse_data

router = APIRouter(tags=["token"], dependencies=[Depends(check_rate_limit)])


@router.get("/token/{token}/validar")
def validar_token(token: str, servico: str = Query(...)):
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT * FROM tokens WHERE token = ?", (token,)
        ).fetchone()

        if row is None:
            return {"valido": False, "motivo": "Token não encontrado."}

        if row["servico"] != servico:
            return {"valido": False, "motivo": "Token não corresponde a este formulário."}

        if row["usado"]:
            return {"valido": False, "motivo": "Este link já foi utilizado."}

        expira_em = parse_data(row["expira_em"])
        if agora() > expira_em:
            return {"valido": False, "motivo": "Este link expirou."}

        return {"valido": True}
    finally:
        conn.close()
