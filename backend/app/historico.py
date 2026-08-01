"""A linha do tempo do atendimento.

No espírito do rastreio dos Correios: cada linha é um evento com hora. Um campo
`status` sozinho diz onde o caso está, mas não como chegou lá — e é justamente o
"aguardando a peça" que faz o cliente mandar mensagem perguntando.

Dois tipos de evento convivem: os **passos**, que o código insere sozinho nos
pontos que já conhece, e os **manuais**, que você escreve quando o caso pede algo
que nenhum passo cobre.
"""

from app.tempo import agora_iso

# Passos pré-definidos. A chave vai no banco; o rótulo é o que o cliente lê.
#
# A ordem aqui é a ordem natural do atendimento e serve para a página desenhar o
# progresso. Passo novo entra no fim desta lista, não no meio: a posição vira
# percentual na barra, e inserir no meio reescreveria o progresso de todo caso
# já em andamento.
PASSOS = {
    "recebido": "Triagem recebida",
    "em_analise": "Em análise",
    "orcamento_enviado": "Orçamento enviado",
    "aguardando_aprovacao": "Aguardando sua aprovação",
    "aguardando_peca": "Aguardando peça",
    "em_execucao": "Em execução",
    "concluido": "Concluído",
}

# O que o cliente escreve pela página dele. Fica fora de PASSOS porque não é
# etapa do atendimento — não avança nada, só registra que ele falou algo.
PASSO_MENSAGEM = "mensagem_cliente"

ORIGENS = {"sistema", "admin", "cliente"}


def rotulo(passo: str) -> str:
    if passo == PASSO_MENSAGEM:
        return "Mensagem do cliente"
    return PASSOS.get(passo, passo)


def registrar_passo(
    conn,
    codigo: str,
    passo: str,
    detalhe: str = "",
    origem: str = "sistema",
    visivel_cliente: bool = True,
) -> None:
    """Acrescenta um evento. Não commita — quem chama decide a transação."""
    conn.execute(
        """
        INSERT INTO historico (codigo, passo, detalhe, origem, visivel_cliente, criado_em)
        VALUES (?,?,?,?,?,?)
        """,
        (codigo, passo, detalhe.strip(), origem, 1 if visivel_cliente else 0, agora_iso()),
    )


def registrar_se_novo(conn, codigo: str, passo: str, detalhe: str = "") -> bool:
    """Registra o passo só se ele ainda não existe para este código.

    Serve aos eventos automáticos, que passam por pontos executados mais de uma
    vez: salvar o atendimento duas vezes não pode encher a linha do tempo do
    cliente com "Em análise" repetido.
    """
    existe = conn.execute(
        "SELECT 1 FROM historico WHERE codigo = ? AND passo = ?", (codigo, passo)
    ).fetchone()
    if existe:
        return False

    registrar_passo(conn, codigo, passo, detalhe)
    return True


def linha_do_tempo(conn, codigo: str, so_visiveis: bool = True) -> list[dict]:
    """Eventos do mais recente para o mais antigo, já com o rótulo resolvido."""
    filtro = "AND visivel_cliente = 1" if so_visiveis else ""
    linhas = conn.execute(
        f"""
        SELECT id, passo, detalhe, origem, visivel_cliente, criado_em
          FROM historico
         WHERE codigo = ? {filtro}
         ORDER BY criado_em DESC, id DESC
        """,
        (codigo,),
    ).fetchall()

    return [{**dict(l), "rotulo": rotulo(l["passo"])} for l in linhas]
