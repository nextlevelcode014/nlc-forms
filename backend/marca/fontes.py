"""Registro das fontes da marca no reportlab.

Por que os `.ttf` estão versionados em `fontes/` em vez de virem do sistema:
o reportlab só lê TrueType. As Poppins instaladas no Linux costumam ser `.otf`
(contornos CFF) e a Inter moderna é fonte variável ou `.ttc` — o `TTFont` não
carrega nenhum dos três. Os arquivos aqui são os estáticos, licença OFL.

Versionar também torna o build do Docker reprodutível: a imagem não depende de
nenhum pacote de fontes do sistema base.
"""

from pathlib import Path

from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

PASTA = Path(__file__).parent / "fontes"

# Nome interno -> arquivo. Os nomes internos são o que se passa em `fontName`.
ARQUIVOS = {
    "Poppins": "Poppins-Regular.ttf",
    "Poppins-Semi": "Poppins-SemiBold.ttf",
    "Poppins-Bold": "Poppins-Bold.ttf",
    "Inter": "Inter-Regular.ttf",
    "Inter-Bold": "Inter-Bold.ttf",
    "Inter-Italic": "Inter-Italic.ttf",
    "Inter-BoldItalic": "Inter-BoldItalic.ttf",
}

_registrado = False


def registrar() -> None:
    """Registra as fontes. Idempotente — pode ser chamado a cada PDF gerado.

    O `registerFontFamily` não é opcional: sem ele o reportlab não sabe qual
    arquivo usar quando o texto do parágrafo traz `<b>` ou `<i>`, e simplesmente
    ignora a marcação. É o que faz negrito e itálico funcionarem no Markdown.
    """
    global _registrado
    if _registrado:
        return

    for nome, arquivo in ARQUIVOS.items():
        pdfmetrics.registerFont(TTFont(nome, str(PASTA / arquivo)))

    # Poppins só tem pesos retos aqui — títulos não usam itálico, então o itálico
    # cai no reto em vez de o reportlab inventar uma inclinação sintética.
    pdfmetrics.registerFontFamily(
        "Poppins",
        normal="Poppins",
        bold="Poppins-Bold",
        italic="Poppins",
        boldItalic="Poppins-Bold",
    )
    pdfmetrics.registerFontFamily(
        "Inter",
        normal="Inter",
        bold="Inter-Bold",
        italic="Inter-Italic",
        boldItalic="Inter-BoldItalic",
    )

    _registrado = True
