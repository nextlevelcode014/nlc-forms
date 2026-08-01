"""Identidade visual dos PDFs da NextLevelCode.

Ponto único de cores, fontes, estilos e template de página. Tanto o PDF de
orçamento (`pdf_relatorio.py`) quanto o relatório em Markdown (`relatorio_md.py`)
importam daqui — é o que impede os dois de divergirem visualmente com o tempo.
"""

from . import cores
from .estilos import MONO, estilos
from .fontes import registrar
from .template import (
    ALTURA,
    CAPA_PADRAO,
    LARGURA,
    LARGURA_UTIL,
    MARGEM_LATERAL,
    CampoCapa,
    DocumentoMarca,
    construir,
)

__all__ = [
    "ALTURA",
    "CAPA_PADRAO",
    "LARGURA",
    "LARGURA_UTIL",
    "MARGEM_LATERAL",
    "MONO",
    "CampoCapa",
    "DocumentoMarca",
    "construir",
    "cores",
    "estilos",
    "registrar",
]
