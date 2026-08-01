"""A linha do tempo do atendimento.

Cada linha é um evento com hora, no espírito do rastreio dos Correios. O que
mudou em relação à primeira versão: **não existe lista de etapas predefinida**.

A versão anterior trazia sete passos fixos — "aguardando peça", "em execução" e
companhia — e a página do cliente desenhava todos, marcando os futuros em
cinza. Isso prometia um caminho que nem sempre existe: um projeto de
desenvolvimento não espera peça nenhuma, e mostrar essa etapa apagada sugeria
que ela ainda viria. Pior, engessava o vocabulário de quem atende.

Agora quem escreve as etapas é você, na hora. A fita começa vazia e só ganha
marcas conforme os eventos acontecem. As sugestões de título vêm do que já foi
usado antes — aprendidas, não decretadas.

O ESTADO ATUAL NÃO É GUARDADO. Ele é sempre o título do último evento visível.
Guardar uma cópia em `execucao.status` foi exatamente o que produziu os bugs que
esta base já teve: um caminho gravava o evento e não o status, e o cliente via o
atendimento parado enquanto ele andava. Sem cópia não há divergência — e apagar
um evento faz o estado voltar sozinho para o anterior.
"""

from app.tempo import agora_iso

ORIGENS = {"sistema", "admin", "cliente"}

# Primeiro evento de toda triagem. É um fato consumado, não uma promessa sobre o
# que vem depois — por isso pode ser fixo sem cair no problema das etapas.
EVENTO_INICIAL = "Triagem recebida"


def registrar_evento(
    conn,
    codigo: str,
    titulo: str,
    detalhe: str = "",
    origem: str = "sistema",
    visivel_cliente: bool = True,
) -> None:
    """Acrescenta um evento. Não commita — quem chama decide a transação."""
    conn.execute(
        """
        INSERT INTO historico (codigo, titulo, detalhe, origem, visivel_cliente, criado_em)
        VALUES (?,?,?,?,?,?)
        """,
        (codigo, titulo.strip(), detalhe.strip(), origem, 1 if visivel_cliente else 0, agora_iso()),
    )


def estado_atual(conn, codigo: str) -> str | None:
    """O título do último evento visível — o que o cliente lê como situação.

    Derivado, nunca guardado. `visivel_cliente = 1` porque uma anotação interna
    sua não é o estado do atendimento aos olhos de quem espera.
    """
    linha = conn.execute(
        """
        SELECT titulo FROM historico
         WHERE codigo = ? AND visivel_cliente = 1
         ORDER BY criado_em DESC, id DESC
         LIMIT 1
        """,
        (codigo,),
    ).fetchone()
    return linha["titulo"] if linha else None


def linha_do_tempo(conn, codigo: str, so_visiveis: bool = True) -> list[dict]:
    """Eventos do mais recente para o mais antigo."""
    filtro = "AND visivel_cliente = 1" if so_visiveis else ""
    linhas = conn.execute(
        f"""
        SELECT id, titulo, detalhe, origem, visivel_cliente, criado_em
          FROM historico
         WHERE codigo = ? {filtro}
         ORDER BY criado_em DESC, id DESC
        """,
        (codigo,),
    ).fetchall()
    return [dict(linha) for linha in linhas]


def titulos_usados(conn, limite: int = 30) -> list[str]:
    """Títulos já usados, do mais frequente para o menos.

    É o que substitui a lista fixa: o painel oferece como sugestão o vocabulário
    que você mesmo criou. Na segunda vez que escrever "Aguardando peça" ele
    aparece pronto; se você nunca esperar peça, ele nunca aparece.
    """
    linhas = conn.execute(
        """
        SELECT titulo, COUNT(*) AS vezes
          FROM historico
         WHERE origem = 'admin'
         GROUP BY titulo
         ORDER BY vezes DESC, MAX(criado_em) DESC
         LIMIT ?
        """,
        (limite,),
    ).fetchall()
    return [linha["titulo"] for linha in linhas]
