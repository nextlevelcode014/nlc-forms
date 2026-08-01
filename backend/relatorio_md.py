"""Relatório em PDF a partir de Markdown, no template da marca.

O documento é gerado **sob demanda** a partir do Markdown guardado no banco, e
não salvo como binário. Assim, quando o template muda, todo relatório antigo
passa a sair no template novo — que é justamente o requisito de "o PDF é sempre
o mesmo da marca".

O caminho é: Markdown -> tokens do markdown-it -> flowables do reportlab.
Trabalhamos sobre o fluxo plano de tokens (`heading_open`, `inline`,
`heading_close`, ...) e não sobre uma árvore, porque é assim que a biblioteca
entrega e porque o mapeamento para flowables é sequencial de qualquer forma.
"""

from __future__ import annotations

import io
import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from xml.sax.saxutils import escape, quoteattr

from markdown_it import MarkdownIt
from markdown_it.token import Token
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import (
    HRFlowable,
    Image,
    KeepTogether,
    ListFlowable,
    ListItem,
    PageBreak,
    Paragraph,
    Preformatted,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.platypus.tableofcontents import TableOfContents

from marca import (
    CAPA_PADRAO,
    LARGURA_UTIL,
    CampoCapa,
    DocumentoMarca,
    construir,
    cores,
    estilos,
)

# Passo único de recuo, em pontos.
#
# Tudo que é subordinado ao texto — marcador de lista, barra de citação, borda do
# bloco de código — começa na margem, e o conteúdo desses blocos recua um passo.
# Assim item de lista, citação e código alinham a primeira letra na mesma coluna,
# e lista aninhada recua exatamente mais um passo.
#
# Antes disso o marcador era desenhado à ESQUERDA da margem (invadindo o branco
# lateral) enquanto o texto do item caía ~30pt para dentro: o marcador avançava e
# o texto fugia, sem hierarquia legível entre os dois.
RECUO = 14

# Onde cada texto entra na arte da capa (`marca/arte/capa.png`).
#
# Coordenadas em milímetros, Y medido a partir do topo — igual às réguas do
# Canva, para dar para transportar os números direto de lá. O Y é a **base** da
# (primeira) linha, que é onde a régua encosta no texto no editor.
#
# Os números saíram de medir `docs/img-examples/1.png`, a arte de referência: a
# margem do texto cai em 21,5 mm e cada bloco está na altura em que o Canva o
# colocou. Este é o único lugar a mexer quando a arte mudar; ver `marca/arte/CAPA.md`.
MARGEM_CAPA = 21.5

CAPA_LAYOUT = {
    "titulo": dict(x=MARGEM_CAPA, y=142, fonte="Poppins-Bold", tamanho=31.5),
    "subtitulo": dict(x=MARGEM_CAPA, y=153, fonte="Inter", tamanho=23),
    # Único campo que quebra sozinho: a descrição vem de texto livre e não dá
    # para prever o comprimento. A largura para antes da faixa diagonal da arte.
    "descricao": dict(
        x=MARGEM_CAPA, y=161, fonte="Inter", tamanho=15.5, largura=162, entrelinha=21.9
    ),
    "rotulo_autores": dict(x=MARGEM_CAPA, y=243, fonte="Inter", tamanho=15),
    "autores": dict(x=MARGEM_CAPA, y=250.5, fonte="Inter", tamanho=15),
    "rotulo_data": dict(x=MARGEM_CAPA, y=267, fonte="Inter", tamanho=15),
    "data": dict(x=MARGEM_CAPA, y=273.5, fonte="Inter", tamanho=15),
    # O código não existe na arte de referência: entra na coluna da direita, na
    # mesma altura da data, para não empurrar nada do que já está lá.
    "rotulo_codigo": dict(x=210 - MARGEM_CAPA, y=267, fonte="Inter", tamanho=15, a_direita=True),
    "codigo": dict(x=210 - MARGEM_CAPA, y=273.5, fonte="Inter", tamanho=15, a_direita=True),
}


def campos_capa(
    titulo: str,
    subtitulo: str = "",
    descricao: str = "",
    autores: str = "",
    data: str = "",
    codigo: str = "",
) -> tuple[CampoCapa, ...]:
    """Textos escritos por cima da arte da capa, nas posições de `CAPA_LAYOUT`.

    Campo vazio simplesmente não é desenhado — inclusive o rótulo dele. É o que
    permite a mesma arte servir a um relatório sem código de atendimento sem
    deixar um "CÓDIGO" solto apontando para o nada.
    """
    campos: list[CampoCapa] = []

    def por(chave: str, texto: str, cor=cores.BRANCO) -> None:
        if texto:
            campos.append(CampoCapa(texto, cor=cor, **CAPA_LAYOUT[chave]))

    por("titulo", titulo)
    por("subtitulo", subtitulo)
    por("descricao", descricao)

    for rotulo, valor, chave in (
        ("Autores:", autores, "autores"),
        ("Data", data, "data"),
        ("Código", codigo, "codigo"),
    ):
        if valor:
            por(f"rotulo_{chave}", rotulo, cor=cores.LARANJA)
            por(chave, valor)

    return tuple(campos)


# Diretório de onde imagens locais do Markdown podem ser lidas. Imagens
# referenciadas por URL não são baixadas: o servidor buscar um endereço que veio
# de um campo de texto é SSRF, e o ganho não paga o risco.
PASTA_IMAGENS = Path(__file__).parent / "relatorios_imagens"


# ── Frontmatter ──────────────────────────────────────────────

def separar_frontmatter(texto: str) -> tuple[dict[str, str], str]:
    """Separa o bloco `---` do topo do corpo do Markdown.

    Aceita apenas `chave: valor` de uma linha — não é YAML de verdade, e é de
    propósito: um parser YAML completo é superfície de ataque desnecessária num
    campo de texto livre, e o que a capa precisa cabe em pares simples.

    O fechamento é procurado **linha a linha**, exigindo uma linha que seja só
    `---`. Uma busca por substring encontraria também o `---` de um separador
    horizontal no meio do texto e trataria dali para a frente como se não
    existisse — o documento perdia todo o conteúdo depois da primeira régua, sem
    erro nenhum.
    """
    linhas = texto.splitlines(keepends=True)
    if not linhas or linhas[0].strip() != "---":
        return {}, texto

    for i, linha in enumerate(linhas[1:], start=1):
        if linha.strip() in ("---", "..."):
            bloco = linhas[1:i]
            corpo = "".join(linhas[i + 1 :]).lstrip("\n")
            break
    else:
        # Abriu o bloco e nunca fechou: é texto comum, não frontmatter.
        return {}, texto

    metadados: dict[str, str] = {}
    for linha in bloco:
        if not linha.strip() or linha.lstrip().startswith("#"):
            continue
        chave, separador, valor = linha.partition(":")
        if separador:
            metadados[chave.strip().lower()] = valor.strip().strip("\"'")

    return metadados, corpo


# ── Renderização ─────────────────────────────────────────────

@dataclass
class _Entrada:
    """Item do sumário, coletado durante a montagem dos flowables."""

    nivel: int
    texto: str
    chave: str


@dataclass
class Renderizador:
    """Converte o fluxo de tokens do markdown-it em flowables do reportlab."""

    estilos: dict = field(default_factory=estilos)
    contadores: list[int] = field(default_factory=lambda: [0, 0, 0])
    entradas: list[_Entrada] = field(default_factory=list)

    def converter(self, markdown: str) -> list:
        # `html: False` não é só endurecimento: com HTML ligado, o markdown-it lê
        # algo como `<atualizados>` — texto legítimo num relatório técnico — como
        # tag e o conteúdo some do PDF sem aviso. Desligado, vira texto comum e
        # é escapado como qualquer outro.
        md = MarkdownIt("commonmark", {"html": False}).enable(["table", "strikethrough"])
        tokens = md.parse(markdown)

        flowables: list = []
        indice = 0
        while indice < len(tokens):
            indice = self._bloco(tokens, indice, flowables)
        return flowables

    # ── Blocos ──────────────────────────────────────────────

    def _bloco(self, tokens: list[Token], i: int, saida: list) -> int:
        token = tokens[i]
        tipo = token.type

        if tipo == "heading_open":
            return self._titulo(tokens, i, saida)
        if tipo == "paragraph_open":
            interno = tokens[i + 1]
            # Um parágrafo que só contém uma imagem vira figura, não texto.
            if self._so_imagem(interno):
                saida.extend(self._imagem(interno.children[0]))
            else:
                saida.append(Paragraph(self._inline(interno), self.estilos["corpo"]))
            return i + 3
        if tipo in ("bullet_list_open", "ordered_list_open"):
            return self._lista(tokens, i, saida)
        if tipo == "table_open":
            return self._tabela(tokens, i, saida)
        if tipo == "blockquote_open":
            return self._citacao(tokens, i, saida)
        if tipo in ("fence", "code_block"):
            saida.append(self._codigo(token.content))
            saida.append(Spacer(1, 10))
            return i + 1
        if tipo == "hr":
            saida.append(Spacer(1, 6))
            saida.append(HRFlowable(width="100%", thickness=0.6, color=cores.LINHA))
            saida.append(Spacer(1, 6))
            return i + 1

        # Token que não vira bloco por si (fechamentos, inline solto).
        return i + 1

    def _titulo(self, tokens: list[Token], i: int, saida: list) -> int:
        nivel = int(tokens[i].tag[1])  # h1 -> 1
        texto = self._inline(tokens[i + 1])

        numero = self._numerar(nivel)
        chave = f"sec-{numero.replace('.', '-')}"

        estilo = self.estilos.get(f"h{min(nivel, 3)}", self.estilos["h3"])
        paragrafo = Paragraph(f"{numero} {texto}", estilo)

        # Lidos depois pelo afterFlowable do documento, que é quem sabe em que
        # página o flowable acabou caindo.
        paragrafo._nivel_toc = nivel  # type: ignore[attr-defined]
        paragrafo._chave_toc = chave  # type: ignore[attr-defined]
        paragrafo._texto_toc = f"{numero} {re.sub(r'<[^>]+>', '', texto)}"  # type: ignore[attr-defined]

        if nivel == 1:
            # Régua azul sob o H1, presa ao título: `KeepTogether` impede que a
            # linha fique órfã no topo da página seguinte.
            saida.append(
                KeepTogether([
                    paragrafo,
                    HRFlowable(width="100%", thickness=1.6, color=cores.AZUL, spaceAfter=8),
                ])
            )
        else:
            saida.append(paragrafo)

        return i + 3

    def _numerar(self, nivel: int) -> str:
        """Numeração automática: o autor escreve `# Diagnóstico`, sai `1. Diagnóstico`.

        Manter a numeração aqui e não no Markdown significa que reordenar seções
        não obriga a renumerar tudo na mão.
        """
        indice = min(nivel, 3) - 1
        self.contadores[indice] += 1
        for seguinte in range(indice + 1, 3):
            self.contadores[seguinte] = 0

        partes = [str(n) for n in self.contadores[: indice + 1]]
        return ".".join(partes) + ("." if indice == 0 else "")

    def _lista(self, tokens: list[Token], i: int, saida: list) -> int:
        ordenada = tokens[i].type == "ordered_list_open"
        fim = self._fechamento(tokens, i)

        itens: list[ListItem] = []
        j = i + 1
        while j < fim:
            if tokens[j].type == "list_item_open":
                fim_item = self._fechamento(tokens, j)
                interno: list = []
                k = j + 1
                while k < fim_item:
                    k = self._bloco(tokens, k, interno)
                if interno:
                    # Sem leftIndent próprio: o recuo é do ListFlowable. Somando
                    # os dois, o texto do item ia parar ~30pt para dentro.
                    itens.append(ListItem(interno))
                j = fim_item + 1
            else:
                j += 1

        if itens:
            saida.append(
                ListFlowable(
                    itens,
                    bulletType="1" if ordenada else "bullet",
                    bulletFontName="Inter",
                    bulletFontSize=9,
                    # Marcador laranja: o acento pontual da marca aparece aqui em
                    # doses pequenas ao longo do texto.
                    bulletColor=cores.LARANJA,
                    leftIndent=RECUO,
                    # `bulletDedent` é o quanto o marcador recua à esquerda do
                    # conteúdo. Igualando ao recuo, ele cai exatamente na margem
                    # em vez de invadir o branco lateral.
                    bulletDedent=RECUO,
                    spaceAfter=8,
                )
            )
        return fim + 1

    def _citacao(self, tokens: list[Token], i: int, saida: list) -> int:
        fim = self._fechamento(tokens, i)
        interno: list = []
        j = i + 1
        while j < fim:
            j = self._bloco(tokens, j, interno)

        # Barra laranja à esquerda, desenhada como borda de uma tabela de 1 célula.
        tabela = Table([[interno]], colWidths=[LARGURA_UTIL])
        tabela.setStyle(
            TableStyle([
                ("LINEBEFORE", (0, 0), (0, -1), 2, cores.LARANJA),
                # Barra na margem, texto um passo para dentro: a citação alinha
                # com o texto dos itens de lista.
                ("LEFTPADDING", (0, 0), (-1, -1), RECUO),
                ("RIGHTPADDING", (0, 0), (-1, -1), RECUO),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ])
        )
        saida.append(tabela)
        saida.append(Spacer(1, 8))
        return fim + 1

    def _codigo(self, conteudo: str) -> Table:
        bloco = Preformatted(conteudo.rstrip("\n"), self.estilos["codigo"])
        tabela = Table([[bloco]], colWidths=[LARGURA_UTIL])
        tabela.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), cores.CINZA_QUIET),
                ("BOX", (0, 0), (-1, -1), 0.5, cores.LINHA),
                # Mesmo passo da citação e da lista — a primeira letra dos três
                # cai na mesma coluna.
                ("LEFTPADDING", (0, 0), (-1, -1), RECUO),
                ("RIGHTPADDING", (0, 0), (-1, -1), RECUO),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ])
        )
        return tabela

    def _tabela(self, tokens: list[Token], i: int, saida: list) -> int:
        fim = self._fechamento(tokens, i)

        linhas: list[list[str]] = []
        cabecalho = False
        j = i + 1
        while j < fim:
            tipo = tokens[j].type
            if tipo == "tr_open":
                fim_linha = self._fechamento(tokens, j)
                celulas = [
                    self._inline(tokens[k + 1])
                    for k in range(j + 1, fim_linha)
                    if tokens[k].type in ("th_open", "td_open")
                ]
                if celulas:
                    if not linhas and tokens[j + 1].type == "th_open":
                        cabecalho = True
                    linhas.append(celulas)
                j = fim_linha + 1
            else:
                j += 1

        if linhas:
            saida.append(self._montar_tabela(linhas, cabecalho))
            saida.append(Spacer(1, 10))
        return fim + 1

    def _montar_tabela(self, linhas: list[list[str]], cabecalho: bool) -> Table:
        colunas = max(len(linha) for linha in linhas)
        normalizadas = [linha + [""] * (colunas - len(linha)) for linha in linhas]

        estilo_topo = self.estilos["tabela_titulo"].clone("topo")
        estilo_topo.textColor = colors.white

        dados = [
            [
                Paragraph(
                    celula,
                    estilo_topo if (cabecalho and n == 0) else self.estilos["tabela_celula"],
                )
                for celula in linha
            ]
            for n, linha in enumerate(normalizadas)
        ]

        tabela = Table(
            dados,
            colWidths=self._larguras(normalizadas, colunas),
            # Cabeçalho repetido no topo de cada página; sem isso uma tabela
            # longa perde o significado das colunas na quebra.
            repeatRows=1 if cabecalho else 0,
        )

        comandos = [
            ("GRID", (0, 0), (-1, -1), 0.5, cores.LINHA),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 7),
            ("RIGHTPADDING", (0, 0), (-1, -1), 7),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]

        if cabecalho:
            comandos += [
                ("BACKGROUND", (0, 0), (-1, 0), cores.TABELA_TOPO),
                ("ALIGN", (0, 0), (-1, 0), "CENTER"),
            ]
            # Zebra a partir da primeira linha de dados.
            for n in range(1, len(dados)):
                if n % 2 == 1:
                    comandos.append(("BACKGROUND", (0, n), (-1, n), cores.ZEBRA))

        tabela.setStyle(TableStyle(comandos))
        return tabela

    @staticmethod
    def _larguras(linhas: list[list[str]], colunas: int) -> list[float]:
        """Distribui a largura pelo tamanho do conteúdo, com piso de 12%.

        Colunas iguais desperdiçam espaço quando uma delas só tem rótulos curtos
        — que é o caso da maioria das tabelas de especificação.
        """
        pesos = []
        for c in range(colunas):
            maior = max((len(linha[c]) for linha in linhas), default=1)
            pesos.append(max(maior, 6))

        total = sum(pesos)
        minimo = 0.12
        fracoes = [max(peso / total, minimo) for peso in pesos]
        soma = sum(fracoes)
        return [LARGURA_UTIL * fracao / soma for fracao in fracoes]

    # ── Imagens ─────────────────────────────────────────────

    @staticmethod
    def _so_imagem(inline: Token) -> bool:
        filhos = [f for f in (inline.children or []) if f.type != "softbreak"]
        return len(filhos) == 1 and filhos[0].type == "image"

    def _imagem(self, token: Token) -> list:
        origem = token.attrGet("src") or ""
        legenda = token.content or token.attrGet("alt") or ""

        caminho = self._resolver_imagem(origem)
        if caminho is None:
            # Nada é baixado da rede: buscar uma URL que veio de campo de texto
            # é SSRF. O leitor vê que existe uma imagem e de onde ela deveria vir.
            texto = f"[imagem não incorporada: {escape(origem)}]"
            return [Paragraph(texto, self.estilos["legenda"]), Spacer(1, 6)]

        imagem = Image(str(caminho))
        proporcao = imagem.drawHeight / imagem.drawWidth
        largura = min(imagem.drawWidth, LARGURA_UTIL)
        imagem.drawWidth = largura
        imagem.drawHeight = largura * proporcao
        imagem.hAlign = "CENTER"

        saida: list = [Spacer(1, 6), imagem]
        if legenda:
            saida.append(Paragraph(escape(legenda), self.estilos["legenda"]))
        saida.append(Spacer(1, 10))
        return saida

    @staticmethod
    def _resolver_imagem(origem: str) -> Path | None:
        """Aceita apenas arquivos dentro de PASTA_IMAGENS.

        O `resolve()` seguido da checagem de prefixo é o que barra `../` — sem
        ele, `![x](../../etc/passwd)` viraria leitura de arquivo arbitrário.
        """
        if not origem or "://" in origem or origem.startswith("data:"):
            return None

        try:
            caminho = (PASTA_IMAGENS / origem).resolve()
            caminho.relative_to(PASTA_IMAGENS.resolve())
        except (ValueError, OSError):
            return None

        return caminho if caminho.is_file() else None

    @staticmethod
    def _fechamento(tokens: list[Token], abertura: int) -> int:
        """Índice do token que fecha o bloco aberto em `abertura`, pelo `nesting`."""
        profundidade = 0
        for i in range(abertura, len(tokens)):
            profundidade += tokens[i].nesting
            if profundidade == 0 and i > abertura:
                return i
        return len(tokens) - 1

    # ── Inline ──────────────────────────────────────────────

    def _inline(self, token: Token) -> str:
        """Converte os filhos de um token inline na mini-marcação do reportlab.

        Todo texto passa por `escape`: um `&` cru derruba o parser do reportlab e
        derrubaria a geração inteira do PDF.
        """
        if token.type != "inline" or not token.children:
            return escape(token.content or "")

        partes: list[str] = []
        for filho in token.children:
            tipo = filho.type

            if tipo == "text":
                partes.append(escape(filho.content))
            elif tipo == "code_inline":
                partes.append(
                    f'<font face="Courier" size="9.5">{escape(filho.content)}</font>'
                )
            elif tipo == "strong_open":
                partes.append("<b>")
            elif tipo == "strong_close":
                partes.append("</b>")
            elif tipo in ("em_open", "s_open"):
                partes.append("<i>" if tipo == "em_open" else "<strike>")
            elif tipo in ("em_close", "s_close"):
                partes.append("</i>" if tipo == "em_close" else "</strike>")
            elif tipo == "link_open":
                destino = filho.attrGet("href") or ""
                partes.append(
                    f"<link href={quoteattr(destino)} color='#1565C0'>"
                )
            elif tipo == "link_close":
                partes.append("</link>")
            elif tipo in ("softbreak", "hardbreak"):
                partes.append("<br/>" if tipo == "hardbreak" else " ")
            elif tipo == "image":
                partes.append(escape(filho.attrGet("alt") or ""))

        return "".join(partes)


# ── Documento ────────────────────────────────────────────────

class _DocumentoRelatorio(DocumentoMarca):
    """Documento que alimenta o sumário conforme os títulos são posicionados."""

    def afterFlowable(self, flowable) -> None:
        nivel = getattr(flowable, "_nivel_toc", None)
        if nivel is None or nivel > 2:
            return

        chave = flowable._chave_toc
        self.canv.bookmarkPage(chave)
        # O sumário só sabe a página depois que o flowable foi colocado — por
        # isso a notificação sai daqui e o build precisa de duas passadas.
        self.notify("TOCEntry", (nivel - 1, flowable._texto_toc, self.page, chave))


def montar_relatorio_md(
    markdown: str,
    titulo: str,
    subtitulo: str = "",
    com_sumario: bool = True,
    campos_capa: Sequence[CampoCapa] = (),
) -> io.BytesIO:
    """Gera o PDF do relatório.

    A capa é a arte de `marca/arte/capa.png`, se o arquivo existir — desenhada como
    imagem de página inteira, com os `campos_capa` escritos por cima. Sem o
    arquivo, o documento abre direto no sumário.
    """

    def criar_doc(buffer: io.BytesIO) -> _DocumentoRelatorio:
        return _DocumentoRelatorio(
            buffer,
            titulo_corrente=subtitulo or titulo,
            capa=CAPA_PADRAO,
            campos_capa=campos_capa,
        )

    def criar_story() -> list:
        # Renderizador novo a cada montagem: ele carrega os contadores de
        # numeração, e reaproveitá-lo faria a segunda passada começar no número
        # em que a primeira parou.
        renderizador = Renderizador()
        corpo = renderizador.converter(markdown)
        if not (com_sumario and corpo):
            return corpo

        e = renderizador.estilos
        sumario = TableOfContents()
        sumario.levelStyles = [e["sumario_1"], e["sumario_2"]]
        sumario.dotsMinLevel = 0

        return [
            Paragraph("Sumário", e["h1"]),
            HRFlowable(width="100%", thickness=1.6, color=cores.AZUL, spaceAfter=12),
            sumario,
            PageBreak(),
            *corpo,
        ]

    # multi=True porque o sumário só sabe as páginas depois de uma passada
    # completa — e cada montagem de `construir` já é, por si, um multiBuild.
    return construir(criar_doc, criar_story, multi=True)
