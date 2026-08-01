"""Acompanhamento público — o rastreio do atendimento.

Substitui o antigo `/consulta`, que devolvia a linha inteira da triagem sem
autenticação: e-mail, telefone, o `token` de acesso e todas as respostas. Quem
tivesse o código lia o dossiê completo do cliente.

Aqui a resposta é montada campo a campo. A regra é: só sai o que o próprio
cliente ganharia perguntando "e aí, como está?" — estado, linha do tempo e o
valor do orçamento. As respostas que ele deu, os dados de contato e qualquer
anotação interna ficam de fora.

O código é a única credencial, por decisão de projeto — é o modelo dos Correios.
Ele tem 8 caracteres de A-Z0-9, ou seja ~2,8 trilhões de combinações, e as rotas
herdam o rate limit do router; adivinhar não é caminho viável.
"""

from fastapi import APIRouter, Depends, HTTPException

from app.config import ROTULO_SERVICO
from app.clientes import atualizar_contato
from app.database import get_db, localizar_por_codigo
from app.historico import estado_atual, linha_do_tempo, registrar_evento
from app.models import ContatoRequest, MensagemClienteRequest
from app.notify import notificar_mensagem_cliente
from app.ratelimit import check_rate_limit

router = APIRouter(tags=["acompanhar"], dependencies=[Depends(check_rate_limit)])

# Recado de cliente é texto livre num endpoint público. O limite não é estético:
# sem ele, o campo vira um jeito barato de encher o SQLite de outra pessoa.
LIMITE_MENSAGEM = 1000


def _exigir_triagem(conn, codigo: str):
    servico, triagem = localizar_por_codigo(conn, codigo)
    if triagem is None:
        raise HTTPException(
            status_code=404,
            detail="Código não encontrado. Confira se digitou exatamente como recebeu.",
        )
    return servico, triagem


@router.get("/acompanhar/{codigo}")
def acompanhar(codigo: str):
    conn = get_db()
    try:
        servico, triagem = _exigir_triagem(conn, codigo)
        execucao = conn.execute(
            "SELECT * FROM execucao WHERE codigo = ?", (codigo,)
        ).fetchone()

        # Só o primeiro nome: confirma para o cliente que o código é o dele
        # sem entregar o nome completo a quem tropeçar num código anotado.
        primeiro_nome = (triagem["cliente_nome"] or "").split(" ")[0]

        # Derivado do último evento visível, nunca guardado.
        estado = estado_atual(conn, codigo)

        orcamento = None
        if execucao and (execucao["valor_total"] or 0) > 0:
            orcamento = {
                "total": execucao["valor_total"],
                "validade": execucao["validade_orcamento"],
            }

        return {
            "codigo": codigo,
            "servico": servico,
            "servico_rotulo": ROTULO_SERVICO.get(servico, servico),
            "cliente": primeiro_nome,
            "aberto_em": triagem["criado_em"],
            "estado": estado,
            "orcamento": orcamento,
            # Curado, não repassado: `linha_do_tempo` traz `id` e
            # `visivel_cliente`, que são controle interno. Repassar o dicionário
            # inteiro é como esta rota nasceu errada da primeira vez.
            #
            # Não existe lista de etapas futuras: a fita da página é montada a
            # partir do que de fato aconteceu. Mostrar etapas em cinza prometia
            # um caminho que nem todo atendimento percorre.
            "historico": [
                {
                    "titulo": e["titulo"],
                    "detalhe": e["detalhe"],
                    "origem": e["origem"],
                    "criado_em": e["criado_em"],
                }
                for e in linha_do_tempo(conn, codigo)
            ],
        }
    finally:
        conn.close()


@router.post("/acompanhar/{codigo}/contato")
def atualizar_contato_publico(codigo: str, data: ContatoRequest):
    """Correção de contato feita pelo cliente.

    Só nome e telefone. O e-mail é a identidade da pasta: deixar um campo público
    reescrevê-lo permitiria mover o histórico de uma pessoa para outra caixa
    postal — quem muda e-mail é você, pelo painel.
    """
    conn = get_db()
    try:
        _, triagem = _exigir_triagem(conn, codigo)

        if not data.nome.strip() and not data.telefone.strip():
            raise HTTPException(status_code=400, detail="Nada para atualizar.")

        atualizar_contato(conn, triagem["cliente_id"], data.nome, data.telefone)
        conn.commit()
        return {"ok": True}
    except HTTPException:
        conn.rollback()
        raise
    finally:
        conn.close()


@router.post("/acompanhar/{codigo}/mensagem", status_code=201)
def mensagem_do_cliente(codigo: str, data: MensagemClienteRequest):
    """Recado do cliente sobre o atendimento — entra na linha do tempo e te avisa.

    É o que substitui o "esqueci de dizer que ele desliga sozinho" perdido no
    WhatsApp: fica registrado no caso, com hora, e visível para os dois lados.
    """
    mensagem = data.mensagem.strip()
    if not mensagem:
        raise HTTPException(status_code=400, detail="Escreva a mensagem antes de enviar.")
    if len(mensagem) > LIMITE_MENSAGEM:
        raise HTTPException(
            status_code=400,
            detail=f"Mensagem muito longa (máximo {LIMITE_MENSAGEM} caracteres).",
        )

    conn = get_db()
    try:
        _, triagem = _exigir_triagem(conn, codigo)
        registrar_evento(conn, codigo, "Mensagem enviada", mensagem, origem="cliente")
        conn.commit()
        nome = triagem["cliente_nome"]
    except HTTPException:
        conn.rollback()
        raise
    finally:
        conn.close()

    # Fora da transação: falha de SMTP não pode desfazer um recado já gravado.
    notificar_mensagem_cliente(codigo, nome, mensagem)

    return {"ok": True}
