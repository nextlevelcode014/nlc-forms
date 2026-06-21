from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query

from app.models import TriagemSuporte, TriagemSeguranca, TriagemDesenvolvimento
from app.auth import validar_e_consumir_token, gerar_codigo_consulta
from app.database import get_db
from app.notify import enviar_notificacao_nova_triagem, notificar_cliente_triagem
from app.ratelimit import check_rate_limit

router = APIRouter(tags=["triagem"], dependencies=[Depends(check_rate_limit)])


@router.post("/triagem/suporte", status_code=201)
def criar_triagem_suporte(data: TriagemSuporte, token: str = Query(...)):
    validar_e_consumir_token(token, "suporte")

    codigo = gerar_codigo_consulta()
    conn = get_db()
    try:
        conn.execute("""
            INSERT INTO triagem_suporte
            (codigo, token, criado_em, nome, email, telefone, problema, quando, causa, tentou,
             marca, modelo, sistema, idade, armazenamento, ram,
             tem_backup, programas, modalidade, observacoes)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            codigo, token, datetime.utcnow().isoformat(),
            data.nome, data.email, data.telefone,
            data.problema, data.quando, data.causa, data.tentou,
            data.marca, data.modelo, data.sistema, data.idade,
            data.armazenamento, data.ram,
            data.tem_backup, data.programas, data.modalidade, data.observacoes,
        ))
        conn.commit()
        enviar_notificacao_nova_triagem("suporte", codigo, data.nome, data.email)
        notificar_cliente_triagem("suporte", codigo, data.nome, data.email)
        return {"ok": True, "mensagem": "Triagem recebida com sucesso.", "codigo": codigo}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


@router.post("/triagem/seguranca", status_code=201)
def criar_triagem_seguranca(data: TriagemSeguranca, token: str = Query(...)):
    validar_e_consumir_token(token, "seguranca")

    codigo = gerar_codigo_consulta()
    conn = get_db()
    try:
        conn.execute("""
            INSERT INTO triagem_seguranca
            (codigo, token, criado_em, nome, email, telefone, perfil, dispositivos, servicos,
             preocupacao, incidente, incidente_desc, usa_2fa, usa_gerenciador,
             tem_backup, modalidade, observacoes)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            codigo, token, datetime.utcnow().isoformat(),
            data.nome, data.email, data.telefone,
            data.perfil, data.dispositivos, data.servicos,
            data.preocupacao, data.incidente, data.incidente_desc,
            data.usa_2fa, data.usa_gerenciador,
            data.tem_backup, data.modalidade, data.observacoes,
        ))
        conn.commit()
        enviar_notificacao_nova_triagem("seguranca", codigo, data.nome, data.email)
        notificar_cliente_triagem("seguranca", codigo, data.nome, data.email)
        return {"ok": True, "mensagem": "Triagem recebida com sucesso.", "codigo": codigo}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


@router.post("/triagem/desenvolvimento", status_code=201)
def criar_triagem_desenvolvimento(data: TriagemDesenvolvimento, token: str = Query(...)):
    validar_e_consumir_token(token, "desenvolvimento")

    codigo = gerar_codigo_consulta()
    conn = get_db()
    try:
        conn.execute("""
            INSERT INTO triagem_desenvolvimento
            (codigo, token, criado_em, nome, email, telefone, tipo_cliente, tipo_projeto,
             descricao, tem_referencia, referencia_url, prazo, orcamento,
             ja_tem_algo, ja_tem_desc, stack_preferida, observacoes)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            codigo, token, datetime.utcnow().isoformat(),
            data.nome, data.email, data.telefone,
            data.tipo_cliente, data.tipo_projeto,
            data.descricao, data.tem_referencia, data.referencia_url,
            data.prazo, data.orcamento,
            data.ja_tem_algo, data.ja_tem_desc,
            data.stack_preferida, data.observacoes,
        ))
        conn.commit()
        enviar_notificacao_nova_triagem("desenvolvimento", codigo, data.nome, data.email)
        notificar_cliente_triagem("desenvolvimento", codigo, data.nome, data.email)
        return {"ok": True, "mensagem": "Triagem recebida com sucesso.", "codigo": codigo}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()
