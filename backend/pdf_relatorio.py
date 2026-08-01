"""Geração de relatório em PDF para o cliente — NextLevelCode.

Estilo "ordem de serviço": seções demarcadas com caixas de cabeçalho,
no espírito de uma OS tradicional de assistência técnica, mas com a
identidade visual da marca (azul/laranja, monospace no código).
"""

import io
from datetime import datetime
from xml.sax.saxutils import escape
from zoneinfo import ZoneInfo

from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, Spacer, Table, TableStyle, HRFlowable

from marca import LARGURA_UTIL, DocumentoMarca, construir, cores, estilos

# Cores e fontes vêm de `marca/`, compartilhadas com o relatório em Markdown.
# Antes existia uma paleta local aqui (#2D8FFF/#F97316) que não batia nem com o
# guia da marca nem com o CSS do site.
COR_PRIMARIA = cores.AZUL
COR_ACCENT = cores.LARANJA
COR_TEXTO = cores.TEXTO
COR_MUTED = cores.MUTED
COR_BORDA = cores.LINHA
COR_SECAO_FUNDO = cores.AZUL_QUIET
COR_FUNDO_TABELA = cores.CINZA_QUIET

FUSO = ZoneInfo("America/Sao_Paulo")

SERVICO_LABEL = {
    "suporte": "Suporte Técnico",
    "seguranca": "Segurança e Privacidade Digital",
    "desenvolvimento": "Desenvolvimento Web e Automação",
}

CAMPOS_TRIAGEM = {
    "suporte": [
        ("Problema relatado", "problema"),
        ("Quando começou", "quando"),
        ("Causa suspeita", "causa"),
        ("Já tentou resolver", "tentou"),
        ("Sistema operacional", "sistema"),
        ("Idade do equipamento", "idade"),
        ("Armazenamento", "armazenamento"),
        ("Memória RAM", "ram"),
        ("Tem backup", "tem_backup"),
        ("Programas essenciais", "programas"),
    ],
    "seguranca": [
        ("Perfil de uso", "perfil"),
        ("Dispositivos", "dispositivos"),
        ("Serviços/contas importantes", "servicos"),
        ("Preocupação principal", "preocupacao"),
        ("Já teve incidente", "incidente"),
        ("Descrição do incidente", "incidente_desc"),
        ("Usa 2FA", "usa_2fa"),
        ("Usa gerenciador de senhas", "usa_gerenciador"),
        ("Faz backup", "tem_backup"),
    ],
    "desenvolvimento": [
        ("Tipo de cliente", "tipo_cliente"),
        ("Tipo de projeto", "tipo_projeto"),
        ("Descrição do projeto", "descricao"),
        ("Tem referência", "tem_referencia"),
        ("Referência", "referencia_url"),
        ("Prazo desejado", "prazo"),
        ("Faixa de orçamento inicial", "orcamento"),
        ("Já tem algo construído", "ja_tem_algo"),
        ("Descrição do existente", "ja_tem_desc"),
        ("Stack preferida", "stack_preferida"),
    ],
}



def _fmt_brl(valor: float) -> str:
    texto = f"{valor:,.2f}"
    texto = texto.replace(",", "_").replace(".", ",").replace("_", ".")
    return f"R$ {texto}"


def _fmt_data(iso_str: str) -> str:
    """Formata um instante gravado em UTC no horário de Brasília.

    O banco guarda tudo em UTC ingênuo (é o certo: um só referencial). Sem a
    conversão aqui, toda data no PDF do cliente saía 3h adiantada.
    """
    if not iso_str:
        return "—"
    try:
        dt = datetime.fromisoformat(iso_str)
    except (ValueError, TypeError):
        return iso_str

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ZoneInfo("UTC"))
    return dt.astimezone(FUSO).strftime("%d/%m/%Y às %H:%M")


def _txt(valor) -> str:
    """Escapa texto de origem externa antes de virar `Paragraph`.

    O reportlab lê o conteúdo do parágrafo como mini-HTML: um `&` cru levanta
    exceção e derruba a geração inteira, e `<algo>` some do documento. Isso vale
    para tudo que o cliente digitou no formulário.
    """
    return escape(str(valor)) if valor not in (None, "") else "—"


def _build_styles():
    """Estilos deste documento, derivados dos da marca.

    A base vem de `marca.estilos()` (Poppins nos títulos, Inter no corpo); aqui
    só ficam os poucos estilos que existem no formato de ordem de serviço e não
    no relatório longo — total, cabeçalho da O.S. e rodapé legal.
    """
    styles = estilos()

    def variacao(origem: str, nome: str, **mudancas) -> ParagraphStyle:
        estilo = styles[origem].clone(nome)
        for atributo, valor in mudancas.items():
            setattr(estilo, atributo, valor)
        return estilo

    styles["brand"] = variacao(
        "h2", "brand", fontName="Poppins-Bold", fontSize=15, textColor=cores.AZUL_TEXTO,
        spaceBefore=0, spaceAfter=0,
    )
    styles["doc_titulo"] = variacao(
        "h3", "doc_titulo", fontSize=13, alignment=TA_RIGHT, spaceBefore=0, spaceAfter=0,
    )
    styles["secao_header"] = variacao("secao", "secao_header")
    styles["campo_label"] = variacao("campo_rotulo", "campo_label", fontSize=9)
    # `corpo` do documento longo é justificado; na O.S. os blocos são curtos e o
    # alinhamento à esquerda evita rios de espaço em parágrafos de duas linhas.
    styles["corpo"] = variacao(
        "corpo", "corpo_os", fontSize=9.5, leading=14, alignment=TA_LEFT, spaceAfter=0,
    )
    styles["bullet_header"] = variacao(
        "h3", "bullet_header", fontSize=9.5, spaceBefore=4, spaceAfter=3,
    )
    styles["rodape"] = variacao(
        "legenda", "rodape", fontSize=7.5, textColor=COR_MUTED, alignment=TA_CENTER,
    )
    styles["total_label"] = variacao(
        "campo_valor", "total_label", fontName="Poppins-Semi", fontSize=11, alignment=TA_RIGHT,
    )
    styles["total_valor"] = variacao(
        "campo_valor", "total_valor", fontName="Poppins-Bold", fontSize=14,
        textColor=COR_ACCENT, alignment=TA_RIGHT,
    )
    styles["tabela_header"] = variacao(
        "tabela_titulo", "tabela_header", fontSize=8.5, textColor=COR_MUTED,
    )
    styles["tabela_valor"] = variacao("tabela_celula", "tabela_valor", fontSize=9)
    return styles


def _secao_header(texto: str, styles) -> Table:
    """Caixa de cabeçalho de seção (fundo azul claro, texto centralizado),
    no espírito do modelo de ordem de serviço de referência."""
    t = Table(
        [[Paragraph(texto.upper(), styles["secao_header"])]],
        colWidths=[LARGURA_UTIL],
    )
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), COR_SECAO_FUNDO),
        ("BOX", (0, 0), (-1, -1), 0.75, COR_BORDA),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    return t


def _campos_box(linhas: list, styles, col_widths=None) -> Table:
    """Caixa com borda e linhas de campo/valor, estilo formulário preenchido."""
    if col_widths is None:
        col_widths = [45 * mm, LARGURA_UTIL - 45 * mm]

    formatadas = []
    for label, valor in linhas:
        formatadas.append([
            Paragraph(f"{escape(label)}:", styles["campo_label"]),
            Paragraph(_txt(valor), styles["campo_valor"]),
        ])

    t = Table(formatadas, colWidths=col_widths)
    estilo = [
        ("BOX", (0, 0), (-1, -1), 0.75, COR_BORDA),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
    ]
    for i in range(len(formatadas) - 1):
        estilo.append(("LINEBELOW", (0, i), (-1, i), 0.5, COR_BORDA))
    t.setStyle(TableStyle(estilo))
    return t


def montar_pdf_relatorio(servico: str, triagem: dict, execucao: dict) -> io.BytesIO:
    """Monta o PDF de orçamento / O.S. Devolve o buffer no início."""
    codigo_doc = triagem.get("codigo", "—")

    return construir(
        lambda buffer: DocumentoMarca(
            buffer, titulo_corrente=f"Orçamento / O.S. · {codigo_doc}"
        ),
        lambda: _montar_story(servico, triagem, execucao),
    )


def _montar_story(servico: str, triagem: dict, execucao: dict) -> list:
    """Flowables do documento.

    É uma função, e não uma lista pronta, porque o reportlab consome os flowables
    ao diagramar — e `construir()` monta o documento duas vezes.
    """
    styles = _build_styles()
    story = []

    servico_label = SERVICO_LABEL.get(servico, servico)
    codigo = triagem.get("codigo", "—")
    validade = execucao.get("validade_orcamento", "")

    # ── Cabeçalho: marca à esquerda, código/data à direita ──
    cab = Table(
        [[
            Paragraph(
                "NextLevelCode<br/><font size=8 color='#555555'>"
                "Suporte técnico · Segurança digital · Desenvolvimento</font>",
                styles["brand"],
            ),
            Paragraph(
                f"ORÇAMENTO / O.S.<br/><font face='Courier-Bold' size=12 color='#FF7A00'>"
                f"{escape(str(codigo))}</font>",
                styles["doc_titulo"],
            ),
        ]],
        colWidths=[LARGURA_UTIL * 0.55, LARGURA_UTIL * 0.45],
    )
    cab.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ALIGN", (1, 0), (1, 0), "RIGHT"),
    ]))
    story.append(cab)
    story.append(Spacer(1, 4))
    story.append(HRFlowable(width="100%", thickness=1.2, color=COR_PRIMARIA, spaceAfter=10))

    # ── Seção: Cliente ──
    story.append(_secao_header("Dados do Cliente", styles))
    linhas_cliente = [
        ("Nome", triagem.get("nome", "—")),
        ("E-mail", triagem.get("email", "—")),
        ("WhatsApp", triagem.get("telefone") or "—"),
        ("Data da solicitação", _fmt_data(triagem.get("criado_em", ""))),
        ("Serviço", servico_label),
    ]
    story.append(_campos_box(linhas_cliente, styles))
    story.append(Spacer(1, 10))

    # ── Seção: Detalhes da solicitação ──
    story.append(_secao_header("Detalhes da Solicitação", styles))
    campos = CAMPOS_TRIAGEM.get(servico, [])
    linhas_detalhes = []

    if servico == "suporte":
        marca = triagem.get("marca", "")
        modelo = triagem.get("modelo", "")
        linhas_detalhes.append(("Marca / modelo", f"{marca} {modelo}".strip() or "—"))

    for label, chave in campos:
        valor = triagem.get(chave)
        if valor:
            linhas_detalhes.append((label, valor))

    if triagem.get("modalidade"):
        linhas_detalhes.append(("Modalidade de atendimento", triagem.get("modalidade")))
    if triagem.get("observacoes"):
        linhas_detalhes.append(("Observações do cliente", triagem.get("observacoes")))

    story.append(_campos_box(linhas_detalhes, styles))
    story.append(Spacer(1, 10))

    # ── Seção: Diagnóstico e atendimento ──
    story.append(_secao_header("Diagnóstico e Atendimento", styles))

    conteudo_diag = []
    for rotulo, chave, espaco in (
        ("Diagnóstico", "diagnostico", 6),
        ("Serviços realizados", "servicos_realizados", 6),
        ("Recomendações", "recomendacoes", 4),
    ):
        if execucao.get(chave):
            conteudo_diag.append(Paragraph(rotulo, styles["bullet_header"]))
            conteudo_diag.append(Paragraph(_txt(execucao[chave]), styles["corpo"]))
            conteudo_diag.append(Spacer(1, espaco))

    # Texto livre: o estado vem do último evento do histórico, escrito à mão.
    # Não há mais um mapa de rótulos porque não há mais lista fixa de etapas.
    status = execucao.get("estado") or "—"
    rodape_status = f"<b>Status:</b> {escape(str(status))}"
    if execucao.get("data_atendimento"):
        rodape_status += (
            f"  ·  <b>Data do atendimento:</b> {_txt(execucao['data_atendimento'])}"
        )
    conteudo_diag.append(Paragraph(rodape_status, styles["corpo"]))

    box_diag = Table([[conteudo_diag]], colWidths=[LARGURA_UTIL])
    box_diag.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.75, COR_BORDA),
        ("TOPPADDING", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(box_diag)
    story.append(Spacer(1, 10))

    # ── Seção: Valores do orçamento ──
    itens = execucao.get("itens", [])
    if itens:
        story.append(_secao_header("Valores do Orçamento", styles))

        cabecalho = [
            Paragraph("Item", styles["tabela_header"]),
            Paragraph("Qtd.", styles["tabela_header"]),
            Paragraph("Valor unit.", styles["tabela_header"]),
            Paragraph("Subtotal", styles["tabela_header"]),
        ]
        linhas_orcamento = [cabecalho]

        for item in itens:
            qtd = item.get("quantidade", 1)
            valor_unit = item.get("valor_unitario", 0)
            subtotal = qtd * valor_unit
            linhas_orcamento.append([
                Paragraph(_txt(item.get("nome", "")), styles["tabela_valor"]),
                Paragraph(str(qtd), styles["tabela_valor"]),
                Paragraph(_fmt_brl(valor_unit), styles["tabela_valor"]),
                Paragraph(_fmt_brl(subtotal), styles["tabela_valor"]),
            ])

        t_orcamento = Table(
            linhas_orcamento,
            colWidths=[85 * mm, 15 * mm, 30 * mm, 40 * mm],
        )
        t_orcamento.setStyle(TableStyle([
            ("BOX", (0, 0), (-1, -1), 0.75, COR_BORDA),
            ("BACKGROUND", (0, 0), (-1, 0), COR_FUNDO_TABELA),
            ("LINEBELOW", (0, 0), (-1, 0), 0.75, COR_BORDA),
            ("LINEBELOW", (0, 1), (-1, -2), 0.4, COR_BORDA),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]))
        story.append(t_orcamento)

        valor_total = execucao.get("valor_total", 0)
        texto_validade = f"Garantia válida até: <b>{_txt(validade)}</b>" if validade else ""

        t_rodape_valores = Table(
            [[
                Paragraph(texto_validade, styles["corpo"]),
                Paragraph("Valor Total", styles["total_label"]),
                Paragraph(_fmt_brl(valor_total), styles["total_valor"]),
            ]],
            colWidths=[75 * mm, 55 * mm, 40 * mm],
        )
        t_rodape_valores.setStyle(TableStyle([
            ("BOX", (0, 0), (-1, -1), 0.75, COR_BORDA),
            ("TOPPADDING", (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]))
        story.append(t_rodape_valores)
        story.append(Spacer(1, 10))

    story.append(Spacer(1, 16))
    story.append(HRFlowable(width="100%", thickness=0.5, color=COR_BORDA, spaceAfter=6))
    # Import tardio: `app.tempo` puxa `app/__init__`, que importa os routers, que
    # importam este módulo. No topo do arquivo isso é um ciclo — e só não
    # explodia porque, na prática, `app` sempre era importado primeiro.
    from app.tempo import agora_iso

    story.append(Paragraph(
        f"NextLevelCode — documento gerado em {_fmt_data(agora_iso())} · "
        f"código de consulta {escape(str(codigo))}",
        styles["rodape"],
    ))
    story.append(Paragraph(
        "Este documento reflete o atendimento prestado e os valores acordados para o serviço descrito.",
        styles["rodape"],
    ))

    return story
