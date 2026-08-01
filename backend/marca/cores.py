"""Paleta da marca para os PDFs.

Fonte da verdade: `guia-marca.md` na raiz do repositório.

Antes de este módulo existir, `pdf_relatorio.py` tinha a própria lista de cores
(`#2D8FFF`, `#F97316`) que não batia com o guia nem com o CSS do site. Cor nova
entra aqui; nenhum gerador declara `HexColor` por conta própria.
"""

from reportlab.lib.colors import HexColor

# ── Marca ────────────────────────────────────────────────────
NAVY = HexColor("#020511")
AZUL = HexColor("#2196F3")
LARANJA = HexColor("#FF7A00")
BRANCO = HexColor("#FFFFFF")

# Azul cru sobre branco dá 3,1:1 — abaixo do mínimo de 4,5:1 para texto.
# Este é o mesmo azul escurecido que o site usa em `--accent` no tema claro.
AZUL_TEXTO = HexColor("#1565C0")

# ── Texto sobre papel ────────────────────────────────────────
TEXTO = HexColor("#222222")
MUTED = HexColor("#555555")
FAINT = HexColor("#9AA0AC")

# ── Papel e preenchimentos ───────────────────────────────────
# Papel levemente azulado em vez de branco puro — tira o brilho na leitura em
# tela e amarra as páginas de corpo ao navy da capa.
PAPEL = HexColor("#F6F8FC")
LINHA = HexColor("#DDDDDD")
AZUL_QUIET = HexColor("#EAF2FE")
CINZA_QUIET = HexColor("#EDF0F6")  # fundo de bloco de código
ZEBRA = HexColor("#E8EBF1")  # linha alternada de tabela

# Cabeçalho de tabela em grafite, como no template de referência: contraste alto
# com o texto branco sem gastar o azul, que fica reservado para as réguas.
TABELA_TOPO = HexColor("#33373F")

# ── Geometria ────────────────────────────────────────────────
# 58° é o ângulo do traço do logo; repetir esse ângulo nos elementos gráficos
# é o que dá unidade visual entre o PDF, o site e o resto da marca.
ANGULO = 58
