---
titulo: Relatório
subtitulo: Acer Nitro V15 (ANV15-51)
descricao: Diagnóstico térmico, testes de benchmark e resultados obtidos.
autores: Kelvin Souza
data: 31/07/2026
versao: 1.0
---

# Como usar este arquivo

Este documento é a referência de estilos do gerador de relatórios: ele usa,
de propósito, **todos** os blocos que o renderizador entende. Suba-o pelo painel
(*Relatório técnico → Carregar arquivo .md*), gere o PDF e compare — se algum
bloco sair diferente daqui, é regressão.

O bloco entre `---` no topo é o **frontmatter**. Ele preenche os metadados que
você deixar em branco no formulário; o que você digitar no formulário vence o que
está aqui. Chaves reconhecidas: `titulo`, `subtitulo`, `descricao`, `versao` e —
se você tiver arte de capa — `data`.

## Títulos e numeração

A numeração é automática. Você escreve `# Diagnóstico` e sai `1. Diagnóstico`;
reordenar seções não obriga a renumerar nada na mão. São três níveis:

### Este é o terceiro nível

`####` e além caem no estilo do terceiro nível e continuam o mesmo contador —
na prática, use até `###`.

# Texto e marcação inline

Parágrafo comum, justificado, em Inter 11pt com entrelinha 1,6 — a mesma do
site. Dentro dele cabem **negrito**, *itálico*, ***os dois juntos***,
~~riscado~~ e `código inline`.

Links funcionam nas duas formas: [com rótulo](https://nextlevelcode.pro) ou
crus, como <https://nextlevelcode.pro>.

Uma linha terminada em dois espaços força quebra sem abrir parágrafo novo —  
esta frase começou depois de uma quebra dura.

Caracteres que costumam quebrar geradores de PDF são escapados e aparecem
literalmente: A & B, 1 < 2, 3 > 2, e uma tag falsa como <atualizados> continua
visível em vez de sumir.

# Listas

Lista simples, marcador laranja na margem:

- Primeiro item
- Segundo item, com texto longo o bastante para quebrar em mais de uma linha e
  mostrar como a continuação alinha com a primeira letra, não com o marcador
- Terceiro item

Aninhamento recua exatamente um passo por nível:

- Dissipador
  - Limpeza dos fins
  - Troca da pasta térmica
    - Arctic MX-6
- Ventoinhas

Lista numerada, para procedimento:

1. Desmontagem completa
2. Limpeza dos dissipadores
3. Aplicação da pasta térmica
4. Novo ciclo de benchmark

# Tabelas

Cabeçalho em grafite, linhas alternadas, largura das colunas distribuída pelo
conteúdo. Em tabela longa o cabeçalho se repete no topo de cada página.

| Item | Detalhe |
| --- | --- |
| Modelo | Acer Nitro V15 (ANV15-51) |
| Armazenamento | SSD NVMe 512 GB (SM2P41C8-512GC5) |
| RAM | 16 GB DDR5-5600 (2x 8GB A-DATA, dual channel) |
| SO | Windows 11 Pro 64-bit |
| Fonte (PSU) | 135 W |

Tabela com mais colunas, para conferir a distribuição:

| Teste | Antes | Depois | Ganho |
| --- | --- | --- | --- |
| Cinebench R23 (multi) | 8.420 | 11.960 | 42% |
| Temperatura máx. CPU | 97 °C | 78 °C | -19 °C |
| Ruído em carga | alto | moderado | — |

> Alinhamento por coluna (`:--`, `--:`) é aceito pelo Markdown mas ignorado no
> PDF: todas as células saem alinhadas à esquerda.

# Citações e código

Citação, com a barra laranja na margem:

> A máquina não apresentava defeito de hardware — o comportamento era
> inteiramente térmico, causado por pasta ressecada e obstrução dos dissipadores.

Citação aninhada, para quando você cita alguém citando:

> Relato do cliente:
>
> > "Ele desliga sozinho quando eu jogo."

Bloco de código, com fundo e borda:

```bash
sudo hwmonitor --interval 2 --log /var/log/termico.csv
```

O nome da linguagem depois das crases é aceito, mas não há colorização de
sintaxe — o bloco sai em monoespaçada simples.

# Imagens

Imagens vêm de `backend/relatorios_imagens/`. Referencie só o nome do arquivo; o
texto entre colchetes vira a legenda embaixo. A imagem é reduzida para caber na
largura do texto, e ampliada nunca — arquivo pequeno sai pequeno.

![Estrutura das tabelas do sistema](diagrama-exemplo.png)

Endereços da internet **não** são baixados. Uma referência assim:

![Gráfico externo](https://exemplo.com/grafico.png)

vira um aviso no lugar da figura, em vez de o servidor sair buscando um endereço
que veio de um campo de texto.

# Separador e o que não é suportado

A linha abaixo é um `---` no meio do texto:

---

Não são reconhecidos, e aparecem como texto cru: notas de rodapé (`[^1]`),
listas de tarefas (`- [ ]` sai como colchete literal, sem caixa), HTML embutido,
e definições/`<details>`. Se precisar de algum deles, é conversa — nenhum é
difícil, só não estava no escopo.

# Fechamento

O rodapé de cada página traz `Página N/M`, e o sumário é montado a partir dos
títulos de primeiro e segundo nível, com link clicável para cada seção.
