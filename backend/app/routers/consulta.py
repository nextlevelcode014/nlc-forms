from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Header, Query

from app.database import get_db, TABELAS_POR_SERVICO
from app.auth import checar_admin
from app.ratelimit import check_rate_limit

router = APIRouter(tags=["consulta"], dependencies=[Depends(check_rate_limit)])


@router.get("/consulta")
def consultar_triagem(
    codigo: str | None = Query(default=None),
    email: str | None = Query(default=None),
    x_admin_key: str | None = Header(default=None),
):
    if not codigo and not email:
        raise HTTPException(status_code=400, detail="Informe 'codigo' ou 'email' para consultar.")

    if email:
        checar_admin(x_admin_key)

    conn = get_db()
    resultados = []
    try:
        for servico, tabela in TABELAS_POR_SERVICO.items():
            # O contato saiu das tabelas de triagem e vive em `clientes`; o JOIN
            # devolve o mesmo formato de antes para quem consome.
            base = f"""
                SELECT t.*, c.nome, c.email, c.telefone
                  FROM {tabela} t
                  JOIN clientes c ON c.id = t.cliente_id
            """
            if codigo:
                rows = conn.execute(base + " WHERE t.codigo = ?", (codigo,)).fetchall()
            else:
                rows = conn.execute(
                    base + " WHERE c.email = ? ORDER BY t.criado_em DESC",
                    (email.strip().lower(),),
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
