"""Geração de relatório em PDF para o cliente — NextLevelCode.

Estilo "ordem de serviço": seções demarcadas com caixas de cabeçalho,
no espírito de uma OS tradicional de assistência técnica, mas com a
identidade visual da marca (azul/laranja, monospace no código).
"""

import io
from datetime import datetime

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_RIGHT, TA_CENTER
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable,
)

# ── Identidade visual ────────────────────────────────────────
COR_PRIMARIA = HexColor("#2D8FFF")
COR_ACCENT = HexColor("#F97316")
COR_TEXTO = HexColor("#1A1A1A")
COR_MUTED = HexColor("#6B7280")
COR_BORDA = HexColor("#D1D5DB")
COR_SECAO_FUNDO = HexColor("#EAF2FE")   # azul bem claro — cabeçalho de seção
COR_FUNDO_TABELA = HexColor("#F9FAFB")

LARGURA_UTIL = 170 * mm  # A4 (210mm) - 20mm margem esquerda - 20mm margem direita

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

STATUS_LABEL = {
    "pendente": "Pendente",
    "em_andamento": "Em andamento",
    "concluido": "Concluído",
}


def _fmt_brl(valor: float) -> str:
    texto = f"{valor:,.2f}"
    texto = texto.replace(",", "_").replace(".", ",").replace("_", ".")
    return f"R$ {texto}"


def _fmt_data(iso_str: str) -> str:
    if not iso_str:
        return "—"
    try:
        dt = datetime.fromisoformat(iso_str)
        return dt.strftime("%d/%m/%Y às %H:%M")
    except (ValueError, TypeError):
        return iso_str


def _build_styles():
    base = getSampleStyleSheet()
    styles = {}

    styles["brand"] = ParagraphStyle(
        "brand", fontName="Helvetica-Bold", fontSize=15, textColor=COR_PRIMARIA,
    )
    styles["doc_titulo"] = ParagraphStyle(
        "doc_titulo", fontName="Helvetica-Bold", fontSize=13,
        textColor=COR_TEXTO, alignment=TA_RIGHT,
    )
    styles["secao_header"] = ParagraphStyle(
        "secao_header", fontName="Helvetica-Bold", fontSize=10.5,
        textColor=COR_TEXTO, alignment=TA_CENTER,
    )
    styles["campo_label"] = ParagraphStyle(
        "campo_label", fontName="Helvetica-Bold", fontSize=9, textColor=COR_TEXTO,
    )
    styles["campo_valor"] = ParagraphStyle(
        "campo_valor", fontName="Helvetica", fontSize=9.5, textColor=COR_TEXTO, leading=13,
    )
    styles["corpo"] = ParagraphStyle(
        "corpo", fontName="Helvetica", fontSize=9.5, textColor=COR_TEXTO, leading=14,
    )
    styles["bullet_header"] = ParagraphStyle(
        "bullet_header", fontName="Helvetica-Bold", fontSize=9.5, textColor=COR_TEXTO,
        spaceBefore=4, spaceAfter=3,
    )
    styles["rodape"] = ParagraphStyle(
        "rodape", fontName="Helvetica", fontSize=7.5, textColor=COR_MUTED, alignment=TA_CENTER,
    )
    styles["total_label"] = ParagraphStyle(
        "total_label", fontName="Helvetica-Bold", fontSize=11,
        textColor=COR_TEXTO, alignment=TA_RIGHT,
    )
    styles["total_valor"] = ParagraphStyle(
        "total_valor", fontName="Helvetica-Bold", fontSize=14,
        textColor=COR_ACCENT, alignment=TA_RIGHT,
    )
    styles["tabela_header"] = ParagraphStyle(
        "tabela_header", fontName="Helvetica-Bold", fontSize=8.5, textColor=COR_MUTED,
    )
    styles["tabela_valor"] = ParagraphStyle(
        "tabela_valor", fontName="Helvetica", fontSize=9, textColor=COR_TEXTO,
    )
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
            Paragraph(f"{label}:", styles["campo_label"]),
            Paragraph(str(valor) if valor else "—", styles["campo_valor"]),
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
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        topMargin=16 * mm, bottomMargin=16 * mm,
        leftMargin=20 * mm, rightMargin=20 * mm,
    )
    styles = _build_styles()
    story = []

    servico_label = SERVICO_LABEL.get(servico, servico)
    codigo = triagem.get("codigo", "—")
    validade = execucao.get("validade_orcamento", "")

    # ── Cabeçalho: marca à esquerda, código/data à direita ──
    cab = Table(
        [[
            Paragraph(
                "NextLevelCode<br/><font size=8 color='#6B7280'>Suporte técnico · Segurança digital · Desenvolvimento</font>",
                styles["brand"],
            ),
            Paragraph(
                f"ORÇAMENTO / O.S.<br/><font face='Courier-Bold' size=12 color='#F97316'>{codigo}</font>",
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
    if execucao.get("diagnostico"):
        conteudo_diag.append(Paragraph("Diagnóstico", styles["bullet_header"]))
        conteudo_diag.append(Paragraph(execucao["diagnostico"], styles["corpo"]))
        conteudo_diag.append(Spacer(1, 6))

    if execucao.get("servicos_realizados"):
        conteudo_diag.append(Paragraph("Serviços realizados", styles["bullet_header"]))
        conteudo_diag.append(Paragraph(execucao["servicos_realizados"], styles["corpo"]))
        conteudo_diag.append(Spacer(1, 6))

    if execucao.get("recomendacoes"):
        conteudo_diag.append(Paragraph("Recomendações", styles["bullet_header"]))
        conteudo_diag.append(Paragraph(execucao["recomendacoes"], styles["corpo"]))
        conteudo_diag.append(Spacer(1, 4))

    status = STATUS_LABEL.get(execucao.get("status", ""), execucao.get("status", "—"))
    rodape_status = f"<b>Status:</b> {status}"
    if execucao.get("data_atendimento"):
        rodape_status += f"  ·  <b>Data do atendimento:</b> {execucao['data_atendimento']}"
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
                Paragraph(item.get("nome", ""), styles["tabela_valor"]),
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
        texto_validade = f"Orçamento válido até: <b>{validade}</b>" if validade else ""

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

    # ── Observações internas — propositalmente NÃO incluídas no PDF do cliente ──

    # ── Rodapé ──
    story.append(Spacer(1, 16))
    story.append(HRFlowable(width="100%", thickness=0.5, color=COR_BORDA, spaceAfter=6))
    story.append(Paragraph(
        f"NextLevelCode — documento gerado em {_fmt_data(datetime.utcnow().isoformat())} · "
        f"código de consulta {codigo}",
        styles["rodape"],
    ))
    story.append(Paragraph(
        "Este documento reflete o atendimento prestado e os valores acordados para o serviço descrito.",
        styles["rodape"],
    ))

    doc.build(story)
    buffer.seek(0)
    return buffer
