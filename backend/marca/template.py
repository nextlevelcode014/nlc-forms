"""Template de página dos documentos da marca.

Uma página-modelo só: margens de leitura, barra laranja fina na lateral,
cabeçalho corrido e rodapé com "Página N/M".

**Não há capa.** O relatório sai só com o miolo, de propósito: a capa é montada
à parte (Canva) e juntada depois. Gerar uma capa aqui só criaria duas fontes da
verdade para a mesma página.

Sobre o "de M": o reportlab pagina numa passada só e, quando fecha a página 1,
ainda não sabe se o documento terá 3 ou 30 páginas. A saída usada aqui é
`construir()`, que monta o documento duas vezes — a primeira só para contar as
páginas, a segunda já com o total em mãos.

A alternativa comum (guardar o estado de cada página num `Canvas` e reemitir
tudo no `save()`) foi tentada e descartada: ela quebra os destinos criados por
`bookmarkPage`, e todos os links do sumário passam a apontar para a página 1.
"""

from __future__ import annotations

import io
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

from reportlab.lib.colors import Color
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.platypus import BaseDocTemplate, Frame, NextPageTemplate, PageBreak, PageTemplate, Spacer

from . import cores
from .fontes import registrar

LARGURA, ALTURA = A4

MARGEM_LATERAL = 20 * mm
MARGEM_TOPO = 28 * mm  # espaço para o cabeçalho corrido
MARGEM_BASE = 22 * mm  # espaço para o rodapé
LARGURA_UTIL = LARGURA - 2 * MARGEM_LATERAL

LOGO = Path(__file__).parent / "logo.png"

# Arte da capa, exportada de um editor externo. Se o arquivo existir, ele vira a
# primeira página; se não, o documento abre direto no miolo.
#
# Fica numa pasta própria porque essa pasta é montada no container: exportar uma
# capa nova do Canva passa a valer no PDF seguinte, sem rebuild da imagem. O
# resto de `marca/` é código e fonte, que só muda com deploy mesmo.
CAPA_PADRAO = Path(__file__).parent / "arte" / "capa.png"


@dataclass
class CampoCapa:
    """Um texto escrito por cima da arte da capa.

    A coordenada é em milímetros e o Y é medido **do topo** — é como réguas de
    editor gráfico funcionam, então dá para ler a posição no Canva e copiar para
    cá sem inverter nada na cabeça.
    """

    texto: str
    x: float
    y: float
    fonte: str = "Poppins-Bold"
    tamanho: float = 24
    cor: Color = cores.BRANCO
    # Alinha pela direita a partir de (x, y) — útil para blocos encostados na
    # margem direita da arte.
    a_direita: bool = False
    # Largura máxima em mm. Preenchida, o texto quebra em linhas; vazia, ele sai
    # numa linha só, custe o que custar. Só a descrição precisa disso — título e
    # data têm tamanho previsível, e quebrá-los seria erro, não recurso.
    largura: float | None = None
    # Distância entre linhas, em pontos. O padrão de 1,35× é o mesmo do corpo.
    entrelinha: float | None = None


def _quebrar(c, campo: CampoCapa) -> list[str]:
    """Quebra o texto do campo na largura pedida, medindo na fonte de verdade.

    A medição é `stringWidth` e não contagem de caracteres: na Poppins um "W"
    ocupa quase o triplo de um "i", e um limite por número de letras erra o
    suficiente para o texto invadir a faixa diagonal da arte.
    """
    if not campo.largura:
        return [campo.texto]

    limite = campo.largura * mm
    linhas: list[str] = []
    atual = ""

    for palavra in campo.texto.split():
        tentativa = f"{atual} {palavra}".strip()
        if atual and c.stringWidth(tentativa, campo.fonte, campo.tamanho) > limite:
            linhas.append(atual)
            atual = palavra
        else:
            atual = tentativa

    if atual:
        linhas.append(atual)
    return linhas


class DocumentoMarca(BaseDocTemplate):
    """Documento A4 com o cabeçalho e o rodapé padrão da marca."""

    def __init__(
        self,
        buffer: io.BytesIO,
        titulo_corrente: str = "",
        total_paginas: int | None = None,
        capa: Path | None = None,
        campos_capa: Sequence[CampoCapa] = (),
    ):
        registrar()

        super().__init__(
            buffer,
            pagesize=A4,
            leftMargin=MARGEM_LATERAL,
            rightMargin=MARGEM_LATERAL,
            topMargin=MARGEM_TOPO,
            bottomMargin=MARGEM_BASE,
            title=titulo_corrente,
            author="NextLevelCode",
        )

        self.titulo_corrente = titulo_corrente
        # Preenchido por `construir()` na segunda montagem. Sem ele o rodapé
        # mostra só "Página N".
        self.total_paginas = total_paginas

        self.capa = capa if capa and capa.exists() else None
        self.campos_capa = campos_capa

        quadro = Frame(
            MARGEM_LATERAL,
            MARGEM_BASE,
            LARGURA_UTIL,
            ALTURA - MARGEM_TOPO - MARGEM_BASE,
            id="corpo",
            showBoundary=0,
            # O Frame vem com 6pt de padding em cada lado. Com eles, a largura
            # útil real é LARGURA_UTIL - 12, e toda tabela declarada com
            # `colWidths=[LARGURA_UTIL]` não cabe: o reportlab a centraliza, e
            # ela sangra 6pt para dentro das duas margens, desalinhada do texto.
            # Zerar aqui faz LARGURA_UTIL significar o que o nome diz.
            leftPadding=0,
            rightPadding=0,
            topPadding=0,
            bottomPadding=0,
        )
        modelos = [PageTemplate(id="corpo", frames=[quadro], onPage=self._decorar)]

        if self.capa:
            # Quadro vazio: a capa é inteira desenhada no canvas, nada flui nela.
            vazio = Frame(0, 0, LARGURA, ALTURA, id="capa", showBoundary=0)
            modelos.insert(
                0, PageTemplate(id="capa", frames=[vazio], onPage=self._desenhar_capa)
            )

        self.addPageTemplates(modelos)

    def abertura(self) -> list:
        """Flowables que empurram o conteúdo para depois da capa.

        Vazio quando não há capa — daí dá para prefixar a story sem condicional.
        """
        if not self.capa:
            return []
        return [Spacer(1, 1), NextPageTemplate("corpo"), PageBreak()]

    def _desenhar_capa(self, c, doc) -> None:
        c.saveState()

        # A arte cobre a página inteira. `preserveAspectRatio=False` é
        # intencional: a exportação já vem em A4, e esticar de leve é melhor do
        # que deixar uma faixa branca se a proporção não bater no último pixel.
        c.drawImage(
            str(self.capa), 0, 0, width=LARGURA, height=ALTURA,
            preserveAspectRatio=False, mask="auto",
        )

        for campo in self.campos_capa:
            c.setFillColor(campo.cor)
            c.setFont(campo.fonte, campo.tamanho)
            escrever = c.drawRightString if campo.a_direita else c.drawString
            entrelinha = campo.entrelinha or campo.tamanho * 1.35

            # Y do campo é medido do topo; o PDF conta do rodapé. As linhas
            # seguintes descem a partir da primeira, então o Y é a base da
            # primeira linha — o mesmo ponto que se lê na régua do editor.
            for i, linha in enumerate(_quebrar(c, campo)):
                escrever(campo.x * mm, ALTURA - campo.y * mm - i * entrelinha, linha)

        c.restoreState()

    def _decorar(self, c, doc) -> None:
        c.saveState()

        # Papel levemente azulado em vez de branco puro: tira o brilho na leitura
        # em tela sem chegar a parecer colorido na impressão.
        c.setFillColor(cores.PAPEL)
        c.rect(0, 0, LARGURA, ALTURA, stroke=0, fill=1)

        # Fio laranja na lateral — presença da marca em dose mínima, não um
        # elemento gráfico que dispute atenção com o texto.
        c.setFillColor(cores.LARANJA)
        c.rect(0, 0, 1.2 * mm, ALTURA, stroke=0, fill=1)

        self._cabecalho(c)
        self._rodape(c, doc.page)

        c.restoreState()

    def _cabecalho(self, c) -> None:
        if LOGO.exists():
            c.drawImage(
                str(LOGO),
                MARGEM_LATERAL,
                ALTURA - 20 * mm,
                width=7 * mm,
                height=7 * mm,
                mask="auto",
            )

        c.setFillColor(cores.MUTED)
        c.setFont("Poppins-Semi", 8.5)
        c.drawString(MARGEM_LATERAL + 9 * mm, ALTURA - 18 * mm, "NextLevelCode")

        if self.titulo_corrente:
            c.setFillColor(cores.TEXTO)
            c.setFont("Poppins-Semi", 9)
            c.drawRightString(
                LARGURA - MARGEM_LATERAL, ALTURA - 18 * mm, self.titulo_corrente
            )

        c.setStrokeColor(cores.LINHA)
        c.setLineWidth(0.5)
        c.setDash(1, 2)
        c.line(
            MARGEM_LATERAL, ALTURA - 22 * mm, LARGURA - MARGEM_LATERAL, ALTURA - 22 * mm
        )
        c.setDash()

    def _rodape(self, c, pagina: int) -> None:
        texto = (
            f"Página {pagina}/{self.total_paginas}"
            if self.total_paginas
            else f"Página {pagina}"
        )
        c.setFillColor(cores.MUTED)
        c.setFont("Inter", 9)
        c.drawRightString(LARGURA - MARGEM_LATERAL, 12 * mm, texto)


def construir(
    criar_doc: Callable[[io.BytesIO], DocumentoMarca],
    criar_story: Callable[[], list],
    multi: bool = False,
) -> io.BytesIO:
    """Monta o documento duas vezes para que o rodapé saiba o total de páginas.

    `criar_story` é uma função e não uma lista porque o reportlab **consome** os
    flowables ao diagramar: reaproveitar a mesma lista na segunda montagem sai
    truncado ou vazio.

    `multi=True` usa `multiBuild`, necessário quando há sumário — ele só descobre
    em que página cada título caiu depois de uma passada completa.

    A segunda montagem tem exatamente a mesma paginação da primeira: o rodapé é
    desenhado no canvas, não é um flowable, então mudar seu texto não empurra
    conteúdo nenhum.
    """
    contagem = io.BytesIO()
    doc = criar_doc(contagem)
    (doc.multiBuild if multi else doc.build)(doc.abertura() + criar_story())
    total = doc.page

    final = io.BytesIO()
    doc = criar_doc(final)
    doc.total_paginas = total
    (doc.multiBuild if multi else doc.build)(doc.abertura() + criar_story())

    final.seek(0)
    return final
