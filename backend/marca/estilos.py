"""Fábrica de estilos de parágrafo.

A escala tipográfica vem do `guia-marca.md`: Poppins nos títulos, Inter no corpo,
salto mínimo de 4pt entre níveis de hierarquia e no máximo três pesos por página.

Os dois geradores de PDF (orçamento e relatório em Markdown) puxam daqui, então
não existe caminho para eles divergirem visualmente.
"""

from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_RIGHT
from reportlab.lib.styles import ParagraphStyle

from . import cores
from .fontes import registrar

# Não há fonte monoespaçada da marca. Courier é embutida no reportlab, então
# nunca falta — e código em PDF é raro o bastante para não valer +200 KB de TTF.
MONO = "Courier"


def estilos() -> dict[str, ParagraphStyle]:
    """Monta o dicionário de estilos. Registra as fontes se ainda não estiverem."""
    registrar()

    def estilo(nome: str, **kwargs) -> ParagraphStyle:
        return ParagraphStyle(nome, **kwargs)

    return {
        # ── Títulos ──────────────────────────────────────────
        "h1": estilo(
            "h1",
            fontName="Poppins-Bold",
            fontSize=15,
            leading=20,
            textColor=cores.NAVY,
            spaceBefore=18,
            spaceAfter=4,
        ),
        "h2": estilo(
            "h2",
            fontName="Poppins-Semi",
            fontSize=12.5,
            leading=17,
            textColor=cores.NAVY,
            spaceBefore=14,
            spaceAfter=5,
        ),
        "h3": estilo(
            "h3",
            fontName="Poppins-Semi",
            fontSize=11,
            leading=15,
            textColor=cores.TEXTO,
            spaceBefore=10,
            spaceAfter=3,
        ),
        # ── Corpo ────────────────────────────────────────────
        "corpo": estilo(
            "corpo",
            fontName="Inter",
            fontSize=11,
            leading=17.6,  # 1.6 de entrelinha, igual ao site
            textColor=cores.TEXTO,
            alignment=TA_JUSTIFY,
            spaceAfter=8,
        ),
        "corpo_pequeno": estilo(
            "corpo_pequeno",
            fontName="Inter",
            fontSize=9.5,
            leading=14,
            textColor=cores.TEXTO,
        ),
        "lista": estilo(
            "lista",
            fontName="Inter",
            fontSize=11,
            leading=16,
            textColor=cores.TEXTO,
            spaceAfter=3,
        ),
        "citacao": estilo(
            "citacao",
            fontName="Inter-Italic",
            fontSize=10.5,
            leading=16,
            textColor=cores.MUTED,
        ),
        "codigo": estilo(
            "codigo",
            fontName=MONO,
            fontSize=8.5,
            leading=12,
            textColor=cores.TEXTO,
        ),
        "legenda": estilo(
            "legenda",
            fontName="Inter",
            fontSize=8.5,
            leading=12,
            textColor=cores.MUTED,
            alignment=TA_CENTER,
            spaceBefore=4,
        ),
        # ── Tabelas ──────────────────────────────────────────
        "tabela_titulo": estilo(
            "tabela_titulo",
            fontName="Poppins-Semi",
            fontSize=10,
            leading=13,
            textColor=cores.NAVY,
        ),
        "tabela_celula": estilo(
            "tabela_celula",
            fontName="Inter",
            fontSize=10,
            leading=13.5,
            textColor=cores.TEXTO,
        ),
        "tabela_numero": estilo(
            "tabela_numero",
            fontName="Inter",
            fontSize=10,
            leading=13.5,
            textColor=cores.TEXTO,
            alignment=TA_RIGHT,
        ),
        # ── Sumário ──────────────────────────────────────────
        "sumario_1": estilo(
            "sumario_1",
            fontName="Poppins-Semi",
            fontSize=11,
            leading=20,
            textColor=cores.NAVY,
        ),
        "sumario_2": estilo(
            "sumario_2",
            fontName="Inter",
            fontSize=10,
            leading=17,
            textColor=cores.TEXTO,
            leftIndent=14,
        ),
        # ── Campos rotulados (usados pelo PDF de orçamento) ──
        "campo_rotulo": estilo(
            "campo_rotulo",
            fontName="Poppins-Bold",
            fontSize=8,
            leading=11,
            textColor=cores.MUTED,
        ),
        "campo_valor": estilo(
            "campo_valor",
            fontName="Inter",
            fontSize=10,
            leading=14,
            textColor=cores.TEXTO,
        ),
        "secao": estilo(
            "secao",
            fontName="Poppins-Semi",
            fontSize=10.5,
            leading=14,
            textColor=cores.NAVY,
            alignment=TA_CENTER,
        ),
    }
