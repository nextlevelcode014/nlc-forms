from datetime import datetime

from fastapi import APIRouter, HTTPException, Query

from app.database import get_db, TABELAS_POR_SERVICO

router = APIRouter(tags=["consulta"])


@router.get("/consulta")
def consultar_triagem(
    codigo: str | None = Query(default=None),
    email: str | None = Query(default=None),
):
    if not codigo and not email:
        raise HTTPException(status_code=400, detail="Informe 'codigo' ou 'email' para consultar.")

    conn = get_db()
    resultados = []
    try:
        for servico, tabela in TABELAS_POR_SERVICO.items():
            if codigo:
                rows = conn.execute(
                    f"SELECT * FROM {tabela} WHERE codigo = ?", (codigo,)
                ).fetchall()
            else:
                rows = conn.execute(
                    f"SELECT * FROM {tabela} WHERE email = ? ORDER BY criado_em DESC", (email,)
                ).fetchall()

            for r in rows:
                item = dict(r)
                item["servico"] = servico
                resultados.append(item)

        if not resultados:
            raise HTTPException(status_code=404, detail="Nenhuma triagem encontrada.")

        return {"resultados": resultados}
    finally:
        conn.close()
