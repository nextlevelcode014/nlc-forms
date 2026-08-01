# Capa do relatório

Solte aqui um arquivo chamado **`capa.png`** e ele vira a primeira página de todo
relatório gerado. Sem esse arquivo, o documento abre direto no sumário — nenhuma
capa é inventada.

## Como exportar

- **A4 retrato**, 210 × 297 mm.
- 150 dpi (1240 × 1754 px) é o suficiente; 300 dpi (2480 × 3508 px) se a arte
  tiver fotografia. Acima disso só engorda o PDF.
- Exporte **sem os textos que mudam** — título, subtítulo, descrição, autores,
  data e código. Eles são escritos por cima, na hora, com as fontes da marca:
  texto de verdade, selecionável, pesquisável e nítido em qualquer zoom.
- O que nunca muda (fundo, faixas diagonais, barra laranja, logo) pode e deve
  estar embutido na imagem. A palavra "Relatório" **não**: ela é o título, e o
  título varia.

Não dá para "substituir" um placeholder escrito dentro da imagem: PNG é pixel,
não texto. O lugar de cada texto está em `CAPA_LAYOUT`, em `relatorio_md.py`.

Esta pasta é montada no container (`compose.yml`): trocar a arte vale no PDF
seguinte, sem rebuild da imagem.

## O que a capa escreve

| Campo | De onde vem |
| --- | --- |
| título | formulário do painel, ou `titulo:` no frontmatter |
| subtítulo | formulário, ou `subtitulo:` no frontmatter |
| descrição | formulário, ou `descricao:` no frontmatter — quebra em linhas sozinha |
| autores | `autores:` no frontmatter; sem ele, "NextLevelCode" |
| data | `data:` no frontmatter; sem ele, a data em que o relatório foi salvo |
| código | o código do atendimento, automático |

Campo vazio não é desenhado, e o rótulo laranja dele some junto — nada de
"Código" apontando para o nada.

## As posições

Calibradas contra `docs/img-examples/1.png`, a arte de referência: as
coordenadas saíram de medir a imagem pixel a pixel, não de estimativa.

| Bloco | X | Y (base da 1ª linha) | Fonte |
| --- | --- | --- | --- |
| título | 21,5 mm | 142 mm | Poppins Bold 31,5 pt |
| subtítulo | 21,5 mm | 153 mm | Inter 23 pt |
| descrição | 21,5 mm | 161 mm | Inter 15,5 pt, caixa de 162 mm |
| Autores: / valor | 21,5 mm | 243 / 250,5 mm | Inter 15 pt |
| Data / valor | 21,5 mm | 267 / 273,5 mm | Inter 15 pt |
| Código / valor | 188,5 mm, à direita | 267 / 273,5 mm | Inter 15 pt |

O **Y é medido do topo** e marca a linha de base do texto — é onde a régua do
Canva encosta. O PDF por baixo conta a partir do rodapé, mas essa inversão é
feita no código; aqui os números se leem como no editor.

## Ajustando

Monte a capa no Canva **com** os textos, anote a posição de cada um pela régua,
transporte para `CAPA_LAYOUT` e exporte de novo **sem** eles.

Para conferir sem chutar: gere o PDF usando a arte *com* os textos como
`capa.png`. Se as posições estiverem certas, o texto desenhado cai exatamente em
cima do texto da imagem; erro de posição aparece como sombra deslocada.
