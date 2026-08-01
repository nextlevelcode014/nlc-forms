from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.clientes import atualizar_contato, exigir_cliente
from app.historico import registrar_passo
from app.models import TriagemSuporte, TriagemSeguranca, TriagemDesenvolvimento
from app.auth import validar_token, consumir_token, gerar_codigo_consulta
from app.database import get_db, TABELAS_POR_SERVICO
from app.notify import enviar_notificacao_nova_triagem, notificar_cliente_triagem
from app.ratelimit import check_rate_limit
from app.tempo import agora_iso

router = APIRouter(tags=["triagem"], dependencies=[Depends(check_rate_limit)])

# Contato não é resposta de formulário: ele pertence ao cliente. Chega no corpo
# porque o formulário mostra os campos pré-preenchidos e permite correção, mas
# vai para a tabela `clientes`, não para a triagem.
CAMPOS_DE_CONTATO = {"nome", "telefone"}


def _registrar_triagem(servico: str, token: str, data: BaseModel) -> dict:
    """Grava a triagem na pasta do cliente e consome o token, numa transação só.

    Quem diz de quem é a triagem é o `cliente_id` gravado no token, não o que foi
    digitado na tela. É isso que permite o mesmo cliente abrir quantas triagens
    precisar — dois notebooks, dois serviços, dois meses depois — sem virar dois
    clientes, e que um erro de digitação não crie uma pasta fantasma.

    Antes o token era marcado como usado e commitado *antes* do INSERT: se a
    gravação falhasse, o cliente ficava sem triagem e sem link. Só existe um
    commit — ou as duas coisas acontecem, ou nenhuma.
    """
    tabela = TABELAS_POR_SERVICO[servico]
    campos = data.model_dump()
    contato = {c: campos.pop(c, "") for c in CAMPOS_DE_CONTATO}
    codigo = gerar_codigo_consulta()

    conn = get_db()
    try:
        linha_token = validar_token(conn, token, servico)
        cliente = exigir_cliente(conn, linha_token["cliente_id"])

        colunas = ["codigo", "cliente_id", "token", "criado_em", *campos]
        conn.execute(
            f"INSERT INTO {tabela} ({', '.join(colunas)}) "
            f"VALUES ({', '.join('?' * len(colunas))})",
            [codigo, cliente["id"], token, agora_iso(), *campos.values()],
        )

        # Correção de contato feita no formulário vale para a ficha inteira: é a
        # informação mais recente que o cliente deu sobre si.
        atualizar_contato(conn, cliente["id"], contato["nome"], contato["telefone"])

        registrar_passo(conn, codigo, "recebido")
        consumir_token(conn, token)
        conn.commit()
    except HTTPException:
        conn.rollback()
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

    # E-mails ficam fora da transação: uma falha de SMTP não pode desfazer
    # uma triagem que já foi gravada.
    enviar_notificacao_nova_triagem(servico, codigo, cliente["nome"], cliente["email"])
    notificar_cliente_triagem(servico, codigo, cliente["nome"], cliente["email"])

    return {"ok": True, "mensagem": "Triagem recebida com sucesso.", "codigo": codigo}


@router.post("/triagem/suporte", status_code=201)
def criar_triagem_suporte(data: TriagemSuporte, token: str = Query(...)):
    return _registrar_triagem("suporte", token, data)


@router.post("/triagem/seguranca", status_code=201)
def criar_triagem_seguranca(data: TriagemSeguranca, token: str = Query(...)):
    return _registrar_triagem("seguranca", token, data)


@router.post("/triagem/desenvolvimento", status_code=201)
def criar_triagem_desenvolvimento(data: TriagemDesenvolvimento, token: str = Query(...)):
    return _registrar_triagem("desenvolvimento", token, data)
