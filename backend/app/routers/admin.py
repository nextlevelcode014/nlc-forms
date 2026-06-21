import json
import io
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Header, Query
from fastapi.responses import StreamingResponse

from app.config import SERVICOS_VALIDOS, TOKEN_TTL_HOURS
from app.database import get_db, TABELAS_POR_SERVICO
from app.auth import checar_admin, gerar_token
from app.models import GerarTokenRequest, SalvarExecucaoRequest
from app.ratelimit import check_rate_limit
from pdf_relatorio import montar_pdf_relatorio
from app.notify import enviar_pdf_cliente

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
    ttl = data.validade_horas or TOKEN_TTL_HOURS
    criado_em = datetime.utcnow()
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
        agora = datetime.utcnow().isoformat()

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
            (datetime.utcnow().isoformat(), codigo),
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
