"""Clientes — a pasta, e tudo que ela reúne.

Antes o cliente era implícito: cada triagem carregava uma cópia do nome, do
e-mail e do telefone, e a mesma pessoa em dois serviços eram duas linhas sem
relação. Aqui ele é criado por você antes de qualquer formulário e sobrevive a
todos eles.
"""

from fastapi import APIRouter, Depends, Header, HTTPException, Query

from app.auth import checar_admin
from app.clientes import atualizar_contato, criar, exigir_cliente, normalizar_email
from app.database import get_db, TABELAS_POR_SERVICO
from app.models import ClienteRequest
from app.ratelimit import check_rate_limit
from app.tempo import agora_iso

router = APIRouter(tags=["clientes"], dependencies=[Depends(check_rate_limit)])


def _triagens_do_cliente(conn, cliente_id: int) -> list[dict]:
    """As triagens da pasta, de todos os serviços, da mais recente para a antiga."""
    encontradas = []
    for servico, tabela in TABELAS_POR_SERVICO.items():
        linhas = conn.execute(
            f"""
            SELECT t.codigo, t.criado_em,
                   e.valor_total, e.data_atendimento,
                   -- Estado derivado do último evento visível, como no resto do
                   -- sistema: não há coluna `status` para divergir.
                   (SELECT h.titulo FROM historico h
                     WHERE h.codigo = t.codigo AND h.visivel_cliente = 1
                     ORDER BY h.criado_em DESC, h.id DESC LIMIT 1) AS estado
              FROM {tabela} t
              LEFT JOIN execucao e ON e.codigo = t.codigo
             WHERE t.cliente_id = ?
            """,
            (cliente_id,),
        ).fetchall()
        encontradas.extend({**dict(l), "servico": servico} for l in linhas)

    encontradas.sort(key=lambda t: t["criado_em"] or "", reverse=True)
    return encontradas


@router.post("/admin/clientes", status_code=201)
def criar_cliente(data: ClienteRequest, x_admin_key: str | None = Header(default=None)):
    checar_admin(x_admin_key)

    if not data.nome.strip():
        raise HTTPException(status_code=400, detail="O nome é obrigatório.")
    if not normalizar_email(data.email):
        raise HTTPException(status_code=400, detail="O e-mail é obrigatório.")

    conn = get_db()
    try:
        cliente_id = criar(conn, data.nome, data.email, data.telefone, data.notas)
        conn.commit()
        return dict(exigir_cliente(conn, cliente_id))
    finally:
        conn.close()


@router.get("/admin/clientes")
def listar_clientes(
    search: str | None = Query(default=None),
    x_admin_key: str | None = Header(default=None),
):
    """Lista as pastas, com quantas triagens e em quais serviços cada uma tem.

    O `servicos` é o cruzamento que antes exigia uma rota própria: com o cliente
    materializado, saber quem contratou mais de uma coisa virou um COUNT.
    """
    checar_admin(x_admin_key)

    unions = " UNION ALL ".join(
        f"SELECT cliente_id, codigo, criado_em, '{s}' AS servico FROM {tabela}"
        for s, tabela in TABELAS_POR_SERVICO.items()
    )

    where, params = "", []
    if search:
        where = "WHERE c.nome LIKE ? OR c.email LIKE ? OR c.telefone LIKE ?"
        like = f"%{search}%"
        params = [like, like, like]

    conn = get_db()
    try:
        linhas = conn.execute(
            f"""
            SELECT c.*,
                   COUNT(t.codigo)                AS triagens,
                   COUNT(DISTINCT t.servico)      AS servicos_distintos,
                   GROUP_CONCAT(DISTINCT t.servico) AS servicos,
                   MAX(t.criado_em)               AS ultima_triagem
              FROM clientes c
              LEFT JOIN ({unions}) t ON t.cliente_id = c.id
              {where}
             GROUP BY c.id
             ORDER BY COALESCE(MAX(t.criado_em), c.criado_em) DESC
            """,
            params,
        ).fetchall()

        clientes = []
        for linha in linhas:
            item = dict(linha)
            # GROUP_CONCAT devolve "suporte,seguranca"; o painel quer uma lista.
            item["servicos"] = sorted(filter(None, (item["servicos"] or "").split(",")))
            clientes.append(item)

        return {"clientes": clientes, "total": len(clientes)}
    finally:
        conn.close()


@router.get("/admin/clientes/{cliente_id}")
def buscar_cliente(cliente_id: int, x_admin_key: str | None = Header(default=None)):
    checar_admin(x_admin_key)

    conn = get_db()
    try:
        cliente = exigir_cliente(conn, cliente_id)
        triagens = _triagens_do_cliente(conn, cliente_id)
        return {
            "cliente": dict(cliente),
            "triagens": triagens,
            "servicos": sorted({t["servico"] for t in triagens}),
        }
    finally:
        conn.close()


@router.put("/admin/clientes/{cliente_id}")
def atualizar_cliente(
    cliente_id: int,
    data: ClienteRequest,
    x_admin_key: str | None = Header(default=None),
):
    """Atualiza a ficha. Diferente do formulário público, aqui o e-mail pode
    mudar — mover a pasta para outra caixa postal é decisão sua, não do cliente."""
    checar_admin(x_admin_key)

    conn = get_db()
    try:
        exigir_cliente(conn, cliente_id)
        email = normalizar_email(data.email)

        colidiu = conn.execute(
            "SELECT id FROM clientes WHERE email = ? AND id != ?", (email, cliente_id)
        ).fetchone()
        if colidiu:
            raise HTTPException(
                status_code=409, detail="Outro cliente já usa este e-mail."
            )

        conn.execute(
            """
            UPDATE clientes
               SET nome = ?, email = ?, telefone = ?, notas = ?, atualizado_em = ?
             WHERE id = ?
            """,
            (
                data.nome.strip(),
                email,
                data.telefone.strip(),
                data.notas.strip(),
                agora_iso(),
                cliente_id,
            ),
        )
        conn.commit()
        return dict(exigir_cliente(conn, cliente_id))
    finally:
        conn.close()


@router.delete("/admin/clientes/{cliente_id}")
def excluir_cliente(cliente_id: int, x_admin_key: str | None = Header(default=None)):
    """Apaga a pasta inteira: triagens, execuções, relatórios e histórico.

    As triagens e os tokens saem por ON DELETE CASCADE — o migrador liga o
    `PRAGMA foreign_keys`, sem o qual a cláusula seria decorativa. Execução,
    relatórios e histórico se ligam por `codigo`, que não é chave estrangeira,
    então esses vão na mão.
    """
    checar_admin(x_admin_key)

    conn = get_db()
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        exigir_cliente(conn, cliente_id)

        codigos = [t["codigo"] for t in _triagens_do_cliente(conn, cliente_id)]
        for codigo in codigos:
            conn.execute("DELETE FROM historico WHERE codigo = ?", (codigo,))
            conn.execute("DELETE FROM relatorios_md WHERE codigo = ?", (codigo,))
            conn.execute("DELETE FROM execucao WHERE codigo = ?", (codigo,))

        conn.execute("DELETE FROM clientes WHERE id = ?", (cliente_id,))
        conn.commit()

        return {"ok": True, "triagens_removidas": len(codigos)}
    except HTTPException:
        conn.rollback()
        raise
    finally:
        conn.close()
