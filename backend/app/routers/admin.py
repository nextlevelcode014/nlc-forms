import json
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Header, Query
from fastapi.responses import StreamingResponse

from app.config import SERVICOS_VALIDOS, settings
from app.database import get_db, TABELAS_POR_SERVICO
from app.auth import checar_admin, gerar_token
from app.models import GerarTokenRequest, RelatorioMdRequest, SalvarExecucaoRequest
from app.ratelimit import check_rate_limit
from pdf_relatorio import montar_pdf_relatorio
from relatorio_md import campos_capa, montar_relatorio_md, separar_frontmatter
from app.notify import enviar_pdf_cliente
from app.tempo import agora as agora_utc, agora_iso, data_local

router = APIRouter(tags=["admin"], dependencies=[Depends(check_rate_limit)])


@router.post("/admin/gerar-token")
def gerar_token_endpoint(
    data: GerarTokenRequest,
    x_admin_key: str | None = Header(default=None),
):
    checar_admin(x_admin_key)

    if data.servico not in SERVICOS_VALIDOS:
        raise HTTPException(status_code=400, detail=f"Serviço inválido. Use um de: {SERVICOS_VALIDOS}")

    token = gerar_token()
    ttl = data.validade_horas or settings.token_ttl_hours
    criado_em = agora_utc()
    expira_em = criado_em + timedelta(hours=ttl)

    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO tokens (token, servico, criado_em, expira_em, nota) VALUES (?,?,?,?,?)",
            (token, data.servico, criado_em.isoformat(), expira_em.isoformat(), data.nota),
        )
        conn.commit()
    finally:
        conn.close()

    return {
        "token": token,
        "servico": data.servico,
        "expira_em": expira_em.isoformat(),
        "expira_em_horas": ttl,
    }


@router.get("/admin/triagem/{codigo}")
def buscar_triagem_para_painel(
    codigo: str,
    servico: str = Query(...),
    x_admin_key: str | None = Header(default=None),
):
    checar_admin(x_admin_key)

    if servico not in TABELAS_POR_SERVICO:
        raise HTTPException(status_code=400, detail="Serviço inválido.")

    conn = get_db()
    try:
        tabela = TABELAS_POR_SERVICO[servico]
        triagem = conn.execute(
            f"SELECT * FROM {tabela} WHERE codigo = ?", (codigo,)
        ).fetchone()

        if triagem is None:
            raise HTTPException(status_code=404, detail="Triagem não encontrada.")

        execucao = conn.execute(
            "SELECT * FROM execucao WHERE codigo = ?", (codigo,)
        ).fetchone()

        execucao_dict = None
        if execucao:
            execucao_dict = dict(execucao)
            execucao_dict["itens"] = json.loads(execucao_dict["itens_json"] or "[]")

        return {
            "triagem": dict(triagem),
            "servico": servico,
            "execucao": execucao_dict,
        }
    finally:
        conn.close()


@router.get("/admin/catalogo")
def listar_catalogo(
    servico: str = Query(...),
    x_admin_key: str | None = Header(default=None),
):
    checar_admin(x_admin_key)

    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT * FROM catalogo_itens WHERE servico = ? AND ativo = 1 ORDER BY nome",
            (servico,),
        ).fetchall()
        return {"itens": [dict(r) for r in rows]}
    finally:
        conn.close()


@router.post("/admin/execucao")
def salvar_execucao(
    data: SalvarExecucaoRequest,
    x_admin_key: str | None = Header(default=None),
):
    checar_admin(x_admin_key)

    if data.servico not in TABELAS_POR_SERVICO:
        raise HTTPException(status_code=400, detail="Serviço inválido.")

    conn = get_db()
    try:
        tabela = TABELAS_POR_SERVICO[data.servico]
        triagem = conn.execute(
            f"SELECT id FROM {tabela} WHERE codigo = ?", (data.codigo,)
        ).fetchone()
        if triagem is None:
            raise HTTPException(status_code=404, detail="Triagem não encontrada para este código.")

        valor_total = sum(item.quantidade * item.valor_unitario for item in data.itens)
        itens_json = json.dumps([item.model_dump() for item in data.itens], ensure_ascii=False)
        agora = agora_iso()

        existente = conn.execute(
            "SELECT id FROM execucao WHERE codigo = ?", (data.codigo,)
        ).fetchone()

        if existente:
            conn.execute("""
                UPDATE execucao SET
                    status = ?, diagnostico = ?, servicos_realizados = ?,
                    recomendacoes = ?, observacoes_internas = ?,
                    itens_json = ?, valor_total = ?, data_atendimento = ?,
                    validade_orcamento = ?, atualizado_em = ?
                WHERE codigo = ?
            """, (
                data.status, data.diagnostico, data.servicos_realizados,
                data.recomendacoes, data.observacoes_internas,
                itens_json, valor_total, data.data_atendimento,
                data.validade_orcamento, agora, data.codigo,
            ))
        else:
            conn.execute("""
                INSERT INTO execucao
                (codigo, servico, criado_em, atualizado_em, status, diagnostico,
                 servicos_realizados, recomendacoes, observacoes_internas,
                 itens_json, valor_total, data_atendimento, validade_orcamento)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                data.codigo, data.servico, agora, agora, data.status,
                data.diagnostico, data.servicos_realizados, data.recomendacoes,
                data.observacoes_internas, itens_json, valor_total,
                data.data_atendimento, data.validade_orcamento,
            ))

        conn.commit()
        return {"ok": True, "valor_total": valor_total}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


@router.get("/admin/triagens")
def listar_triagens(
    servico: str | None = Query(default=None),
    status: str | None = Query(default=None),
    search: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    x_admin_key: str | None = Header(default=None),
):
    checar_admin(x_admin_key)

    if servico and servico not in TABELAS_POR_SERVICO:
        raise HTTPException(status_code=400, detail="Serviço inválido.")

    servicos = [servico] if servico else list(TABELAS_POR_SERVICO)

    unions = []
    for s in servicos:
        tabela = TABELAS_POR_SERVICO[s]
        unions.append(
            f"SELECT codigo, nome, email, telefone, criado_em, '{s}' as servico FROM {tabela}"
        )
    subconsulta = " UNION ALL ".join(unions)

    conn = get_db()
    try:
        where_clauses = []
        params: list = []

        if search:
            where_clauses.append("(codigo LIKE ? OR nome LIKE ? OR email LIKE ?)")
            like = f"%{search}%"
            params.extend([like, like, like])

        if status:
            where_clauses.append("e.status = ?")
            params.append(status)

        where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

        count_sql = f"""
            SELECT COUNT(*) as total FROM ({subconsulta}) t
            LEFT JOIN execucao e ON e.codigo = t.codigo
            {where_sql}
        """
        total = conn.execute(count_sql, params).fetchone()["total"]

        offset = (page - 1) * per_page
        data_sql = f"""
            SELECT t.*, e.status, e.valor_total, e.data_atendimento
            FROM ({subconsulta}) t
            LEFT JOIN execucao e ON e.codigo = t.codigo
            {where_sql}
            ORDER BY t.criado_em DESC
            LIMIT ? OFFSET ?
        """
        rows = conn.execute(data_sql, params + [per_page, offset]).fetchall()

        return {
            "triagens": [dict(r) for r in rows],
            "total": total,
            "page": page,
            "per_page": per_page,
        }
    finally:
        conn.close()


@router.get("/admin/relatorio/{codigo}.pdf")
def gerar_relatorio_pdf(
    codigo: str,
    servico: str = Query(...),
    x_admin_key: str | None = Header(default=None),
):
    checar_admin(x_admin_key)

    if servico not in TABELAS_POR_SERVICO:
        raise HTTPException(status_code=400, detail="Serviço inválido.")

    conn = get_db()
    try:
        tabela = TABELAS_POR_SERVICO[servico]
        triagem = conn.execute(
            f"SELECT * FROM {tabela} WHERE codigo = ?", (codigo,)
        ).fetchone()
        if triagem is None:
            raise HTTPException(status_code=404, detail="Triagem não encontrada.")

        execucao = conn.execute(
            "SELECT * FROM execucao WHERE codigo = ?", (codigo,)
        ).fetchone()
        if execucao is None:
            raise HTTPException(
                status_code=400,
                detail="Nenhuma execução registrada ainda. Preencha o atendimento antes de gerar o PDF.",
            )

        conn.execute(
            "UPDATE execucao SET pdf_gerado_em = ? WHERE codigo = ?",
            (agora_iso(), codigo),
        )
        conn.commit()

        triagem_dict = dict(triagem)
        execucao_dict = dict(execucao)
        execucao_dict["itens"] = json.loads(execucao_dict["itens_json"] or "[]")

        pdf_buffer = montar_pdf_relatorio(servico, triagem_dict, execucao_dict)

        return StreamingResponse(
            pdf_buffer,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="relatorio-{codigo}.pdf"'
            },
        )
    finally:
        conn.close()


@router.post("/admin/enviar-pdf")
def enviar_pdf_cliente_endpoint(
    codigo: str = Query(...),
    servico: str = Query(...),
    x_admin_key: str | None = Header(default=None),
):
    checar_admin(x_admin_key)

    if servico not in TABELAS_POR_SERVICO:
        raise HTTPException(status_code=400, detail="Serviço inválido.")

    conn = get_db()
    try:
        tabela = TABELAS_POR_SERVICO[servico]
        triagem = conn.execute(
            f"SELECT * FROM {tabela} WHERE codigo = ?", (codigo,)
        ).fetchone()
        if triagem is None:
            raise HTTPException(status_code=404, detail="Triagem não encontrada.")

        execucao = conn.execute(
            "SELECT * FROM execucao WHERE codigo = ?", (codigo,)
        ).fetchone()
        if execucao is None:
            raise HTTPException(status_code=400, detail="Nenhuma execução registrada.")

        triagem_dict = dict(triagem)
        execucao_dict = dict(execucao)
        execucao_dict["itens"] = json.loads(execucao_dict["itens_json"] or "[]")

        pdf_buffer = montar_pdf_relatorio(servico, triagem_dict, execucao_dict)
        pdf_bytes = pdf_buffer.getvalue()

        enviar_pdf_cliente(servico, codigo, triagem_dict["nome"], triagem_dict["email"], pdf_bytes)

        return {"ok": True, "mensagem": f"PDF enviado para {triagem_dict['email']}"}
    finally:
        conn.close()


# ── Relatórios técnicos em Markdown ──────────────────────────
#
# O que fica guardado é o Markdown; o PDF é montado a cada download. Assim uma
# mudança no template da marca vale retroativamente para todo o histórico.


def _resolver_metadados(data: RelatorioMdRequest) -> tuple[dict, str]:
    """Funde o frontmatter do arquivo com o que veio do formulário.

    O formulário ganha: o admin acabou de digitar aquilo, então é a intenção mais
    recente. O frontmatter serve de padrão para o que ele deixou em branco.
    """
    frontmatter, corpo = separar_frontmatter(data.markdown)

    campos = {
        "titulo": data.titulo or frontmatter.get("titulo") or "Relatório",
        "subtitulo": data.subtitulo or frontmatter.get("subtitulo", ""),
        "descricao": data.descricao or frontmatter.get("descricao", ""),
        "versao": data.versao or frontmatter.get("versao", ""),
    }
    return campos, corpo


@router.post("/admin/relatorios-md")
def criar_relatorio_md(
    data: RelatorioMdRequest,
    x_admin_key: str | None = Header(default=None),
):
    checar_admin(x_admin_key)

    if not data.markdown.strip():
        raise HTTPException(status_code=400, detail="O relatório está vazio.")

    campos, _ = _resolver_metadados(data)
    agora = agora_iso()

    conn = get_db()
    try:
        cursor = conn.execute(
            """
            INSERT INTO relatorios_md
                (codigo, titulo, subtitulo, descricao, versao, markdown, criado_em, atualizado_em)
            VALUES (?,?,?,?,?,?,?,?)
            """,
            (
                data.codigo,
                campos["titulo"],
                campos["subtitulo"],
                campos["descricao"],
                campos["versao"],
                data.markdown,
                agora,
                agora,
            ),
        )
        conn.commit()
        return {"id": cursor.lastrowid, "codigo": data.codigo, **campos}
    finally:
        conn.close()


@router.get("/admin/relatorios-md")
def listar_relatorios_md(
    codigo: str = Query(...),
    x_admin_key: str | None = Header(default=None),
):
    checar_admin(x_admin_key)

    conn = get_db()
    try:
        # Sem a coluna `markdown`: a lista não precisa dela e um relatório longo
        # deixaria a resposta pesada à toa.
        linhas = conn.execute(
            """
            SELECT id, codigo, titulo, subtitulo, versao, criado_em, atualizado_em
            FROM relatorios_md WHERE codigo = ?
            ORDER BY atualizado_em DESC
            """,
            (codigo,),
        ).fetchall()
        return {"relatorios": [dict(linha) for linha in linhas]}
    finally:
        conn.close()


# Declarada antes da rota de `{relatorio_id}` para que "12.pdf" não seja
# confundido com um id.
@router.get("/admin/relatorios-md/{relatorio_id}.pdf")
def gerar_relatorio_md_pdf(
    relatorio_id: int,
    x_admin_key: str | None = Header(default=None),
):
    checar_admin(x_admin_key)

    conn = get_db()
    try:
        relatorio = conn.execute(
            "SELECT * FROM relatorios_md WHERE id = ?", (relatorio_id,)
        ).fetchone()
        if relatorio is None:
            raise HTTPException(status_code=404, detail="Relatório não encontrado.")
    finally:
        conn.close()

    frontmatter, corpo = separar_frontmatter(relatorio["markdown"])

    # `autores` vive só no frontmatter, sem coluna própria: quem assina é uma
    # propriedade do texto, não do formulário. E acrescentar coluna hoje não
    # alcançaria os bancos que já existem — o schema é `CREATE TABLE IF NOT
    # EXISTS`, sem mecanismo de migração.
    autores = frontmatter.get("autores") or "NextLevelCode"

    # A capa só existe se `marca/arte/capa.png` estiver no lugar; sem o arquivo, estes
    # campos são ignorados e o documento abre no sumário. Ver `marca/arte/CAPA.md`.
    pdf = montar_relatorio_md(
        corpo,
        titulo=relatorio["titulo"],
        subtitulo=relatorio["subtitulo"] or "",
        campos_capa=campos_capa(
            titulo=relatorio["titulo"],
            subtitulo=relatorio["subtitulo"] or "",
            descricao=relatorio["descricao"] or frontmatter.get("descricao", ""),
            autores=autores,
            data=frontmatter.get("data") or data_local(relatorio["atualizado_em"]),
            codigo=relatorio["codigo"],
        ),
    )

    return StreamingResponse(
        pdf,
        media_type="application/pdf",
        headers={
            "Content-Disposition": (
                f'attachment; filename="relatorio-tecnico-{relatorio["codigo"]}.pdf"'
            )
        },
    )


@router.get("/admin/relatorios-md/{relatorio_id}")
def buscar_relatorio_md(
    relatorio_id: int,
    x_admin_key: str | None = Header(default=None),
):
    checar_admin(x_admin_key)

    conn = get_db()
    try:
        relatorio = conn.execute(
            "SELECT * FROM relatorios_md WHERE id = ?", (relatorio_id,)
        ).fetchone()
        if relatorio is None:
            raise HTTPException(status_code=404, detail="Relatório não encontrado.")
        return dict(relatorio)
    finally:
        conn.close()


@router.put("/admin/relatorios-md/{relatorio_id}")
def atualizar_relatorio_md(
    relatorio_id: int,
    data: RelatorioMdRequest,
    x_admin_key: str | None = Header(default=None),
):
    checar_admin(x_admin_key)

    if not data.markdown.strip():
        raise HTTPException(status_code=400, detail="O relatório está vazio.")

    campos, _ = _resolver_metadados(data)

    conn = get_db()
    try:
        cursor = conn.execute(
            """
            UPDATE relatorios_md
               SET titulo = ?, subtitulo = ?, descricao = ?, versao = ?,
                   markdown = ?, atualizado_em = ?
             WHERE id = ?
            """,
            (
                campos["titulo"],
                campos["subtitulo"],
                campos["descricao"],
                campos["versao"],
                data.markdown,
                agora_iso(),
                relatorio_id,
            ),
        )
        conn.commit()

        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Relatório não encontrado.")

        return {"id": relatorio_id, "codigo": data.codigo, **campos}
    finally:
        conn.close()


@router.delete("/admin/relatorios-md/{relatorio_id}")
def excluir_relatorio_md(
    relatorio_id: int,
    x_admin_key: str | None = Header(default=None),
):
    checar_admin(x_admin_key)

    conn = get_db()
    try:
        cursor = conn.execute(
            "DELETE FROM relatorios_md WHERE id = ?", (relatorio_id,)
        )
        conn.commit()
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Relatório não encontrado.")
        return {"ok": True}
    finally:
        conn.close()
