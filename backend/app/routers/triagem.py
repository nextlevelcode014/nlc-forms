from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.config import ROTULO_SERVICO
from app.models import TriagemSuporte, TriagemSeguranca, TriagemDesenvolvimento
from app.auth import validar_token, consumir_token, gerar_codigo_consulta
from app.database import get_db, TABELAS_POR_SERVICO
from app.notify import enviar_notificacao_nova_triagem, notificar_cliente_triagem
from app.ratelimit import check_rate_limit
from app.tempo import agora_iso

router = APIRouter(tags=["triagem"], dependencies=[Depends(check_rate_limit)])


def _recusar_email_repetido(conn, servico: str, email: str) -> None:
    """Um e-mail só pode ter uma triagem **por serviço**.

    O mesmo cliente pode aparecer em suporte, segurança e desenvolvimento — são
    atendimentos distintos e o cruzamento entre eles é justamente o que o painel
    passa a mostrar. O que não pode é a mesma pessoa abrir duas triagens do mesmo
    serviço e virar dois clientes separados na lista.

    A comparação normaliza caixa e espaço: `Joao@Email.com ` e `joao@email.com`
    são a mesma caixa postal, e deixar as duas entrarem derrotaria a regra.

    Levantar aqui desfaz a transação inteira, então o token **não** é consumido —
    o cliente corrige o e-mail e reenvia pelo mesmo link.
    """
    tabela = TABELAS_POR_SERVICO[servico]
    existe = conn.execute(
        f"SELECT codigo FROM {tabela} WHERE LOWER(TRIM(email)) = LOWER(TRIM(?))",
        (email,),
    ).fetchone()

    if existe is not None:
        rotulo = ROTULO_SERVICO.get(servico, servico)
        raise HTTPException(
            status_code=409,
            detail=(
                f"Este e-mail já tem uma triagem de {rotulo}. "
                "Se você precisa de um novo atendimento, me chame no WhatsApp "
                "antes de preencher de novo."
            ),
        )


def _registrar_triagem(servico: str, token: str, data: BaseModel) -> dict:
    """Grava a triagem e consome o token na mesma transação.

    Antes o token era marcado como usado e commitado *antes* do INSERT: se a
    gravação falhasse, o cliente ficava sem triagem e sem link. Agora só existe
    um commit — ou as duas coisas acontecem, ou nenhuma.

    As colunas do INSERT vêm dos campos do modelo Pydantic (que têm os mesmos
    nomes das colunas), então o f-string não toca em dado enviado pelo usuário.
    """
    tabela = TABELAS_POR_SERVICO[servico]
    campos = data.model_dump()
    colunas = ["codigo", "token", "criado_em", *campos]
    codigo = gerar_codigo_consulta()

    conn = get_db()
    try:
        validar_token(conn, token, servico)
        _recusar_email_repetido(conn, servico, data.email)

        conn.execute(
            f"INSERT INTO {tabela} ({', '.join(colunas)}) "
            f"VALUES ({', '.join('?' * len(colunas))})",
            [codigo, token, agora_iso(), *campos.values()],
        )
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
    enviar_notificacao_nova_triagem(servico, codigo, data.nome, data.email)
    notificar_cliente_triagem(servico, codigo, data.nome, data.email)

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
