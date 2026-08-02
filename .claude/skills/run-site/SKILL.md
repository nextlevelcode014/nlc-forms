---
name: run-site
description: Build, run, and drive the two nlc-forms frontends (public forms and admin panel). Use when asked to start a frontend, run the dev server, build it, check it, take a screenshot of a page, verify a visual change, or audit the rendered pages.
---

Dois projetos Astro 7 em workspaces bun, dentro de `frontend/`:

| projeto | o que é | porta | vai para |
|---|---|---|---|
| `public` | formulários de triagem do cliente | 4321 | Vercel |
| `admin` | painel de atendimento | 9080 | só a tailnet |

Não há suíte de testes no frontend: a verificação é `bun run build` +
`bun run check` para o código, e `.claude/skills/run-site/driver.mjs` para o que
só existe depois do CSS resolver e do JS rodar — contraste, layout, portão de
acesso, palavras coladas.

O driver fala CDP direto por WebSocket, sem Playwright nem Puppeteer. Ele precisa
apenas de um binário Chromium no disco.

**As portas importam.** São as do `ALLOWED_ORIGINS` no `.env` da API; servir em
outra porta faz o navegador barrar por CORS antes da requisição sair.

## Prerequisites

O bun já é o runtime do projeto. Além dele, um Chromium — o driver procura,
nesta ordem: `$BROWSER_BIN`, `/opt/google/chrome/chrome`, `/usr/bin/chromium`,
`/usr/bin/google-chrome`, `/opt/brave.com/brave-origin-beta/brave`.

Nesta máquina (Arch, sem Chrome) o caminho usado é um symlink para o Brave —
ver a seção Gotchas.

## Setup

```bash
cd frontend && bun install
```

Cada projeto lê o endereço da API de `PUBLIC_API_BASE`, no `.env` dele. Sem isso
o build embute a URL da tailnet, que não responde desta máquina:

```bash
echo 'PUBLIC_API_BASE=http://localhost:8000' | tee public/.env admin/.env
```

## Build

```bash
cd frontend
bun run build          # os dois
bun run build:public   # só o público — é o que a Vercel roda
bun run check          # astro check (TypeScript + templates) nos dois
```

Ambos precisam terminar limpos antes de qualquer commit.

## Run (agent path)

O driver **não sobe servidor**. Suba um antes, do projeto que vai auditar:

```bash
cd frontend
bun run build
(bun run --cwd public preview --port 4321 >/tmp/preview-public.log 2>&1 &)
timeout 30 bash -c 'until curl -sf http://localhost:4321/ >/dev/null; do sleep 0.5; done'
```

Para o painel, troque `public` por `admin` e `4321` por `9080`.

Use `preview` (serve o `dist/`) e não `dev` quando for verificar o resultado
final. Para parar:

```bash
ss -lptnH 'sport = :4321' | grep -oE 'pid=[0-9]+' | cut -d= -f2 | sort -u | xargs -r kill
```

`lsof` não está instalado nesta máquina; `ss` (do `iproute2`) está e é o que
funciona. Não use `pkill -f` com padrão amplo — ele casa com a própria linha de
comando do agente e mata a sessão.

### Os portões de acesso

Este é o ponto que separa esta skill de auditar um site comum: **nenhuma página
com conteúdo aparece sozinha**. A triagem só monta o formulário depois de validar
o token na API, e o painel só revela `#protegido` depois da chave de admin. Sem
abrir o portão, a auditoria fotografa a tela "🔒 Acesso restrito" e reporta
sucesso.

Três formas de abrir, da mais barata para a mais fiel:

| flag | precisa da API? | o que você vê |
|---|---|---|
| `--destravar` | não | o formulário/painel montado, com dados vazios |
| `--token <t>` | sim | o fluxo real da triagem |
| `--admin-key <k>` | sim | o painel com a lista de clientes carregada |

`--destravar` força os portões pelo DOM (esconde `#bloqueado`/`#portao`, mostra
`#conteudo`/`#protegido`). É o padrão para trabalho visual — não depende de
container no ar. Use `--admin-key` quando o que você mudou só aparece com dados:
tabela de clientes, tags de status, formulário de atendimento.

Sem nenhuma das três, a auditoria roda com os portões fechados e verifica o
contrário: que o conteúdo protegido **não** está visível. Rode assim de vez em
quando — é a checagem que guarda a promessa de "quem chega sem link não vê nem a
estrutura das perguntas".

```bash
CHAVE=$(grep '^ADMIN_KEY=' .env | cut -d= -f2-)
bun .claude/skills/run-site/driver.mjs audit --projeto admin --admin-key "$CHAVE"
```

Com `SEED_DEMO=true` no `.env` o painel abre com 3 clientes fictícios — é o que
torna a auditoria com login realmente útil.

### Auditar

O comando principal. Percorre as rotas e reporta o que build e `astro check` não
pegam. Sai com código 1 se achar algo.

```bash
bun .claude/skills/run-site/driver.mjs audit --projeto public --destravar
bun .claude/skills/run-site/driver.mjs audit --projeto admin --destravar --theme light
bun .claude/skills/run-site/driver.mjs audit /triagem-suporte.html --destravar
```

Sem rotas na linha de comando, ele varre os `.html` de
`frontend/<projeto>/dist/` — ou seja, **exige `bun run build` antes**, e o que
ele audita acompanha as páginas sozinho. Não mantenha lista de rotas à mão: lista
fixa apodrece e o servidor estático responde a rota morta com a página errada.

Não há sitemap aqui, por isso a fonte das rotas é o `dist/`. Só a home é
indexável; formulário e acompanhamento carregam dado de cliente e saem
`noindex` de propósito — dá para conferir isso no próprio `dist/`:

```bash
grep -o '<meta name="robots"[^>]*>' frontend/public/dist/*.html
```

Cobertura completa antes de dar trabalho visual por concluído — os dois temas
importam porque `tokens.css` tem valores diferentes para cada um:

```bash
for t in dark light; do for w in 1440 390; do
  bun .claude/skills/run-site/driver.mjs audit --projeto public --destravar --width $w --theme $t
done; done
```

Saída verificada: `✓ 5 rota(s) sem problemas` nas quatro combinações. São ~0,5s
por combinação (5 páginas pequenas), então a matriz inteira cabe numa chamada só.
**A auditoria é determinística**: dois números diferentes para a mesma combinação
significam bug no driver, não flutuação — foi assim que os dois gotchas de
medição apareceram.

O que ele detecta:

| checagem | por que existe |
|---|---|
| contraste abaixo de WCAG AA | `tokens.css` escurece azul e laranja no tema claro justamente porque os hex do guia dão 3,1:1 e 2,6:1 sobre branco; a checagem impede alguém de "corrigir" para o valor do guia e rebaixar a leitura |
| portão vazado | conteúdo protegido visível sem credencial — a triagem não pode mostrar as perguntas, o painel não pode mostrar dado de cliente |
| campo sem rótulo | formulário É o produto aqui; sem `<label for>` o leitor de tela não anuncia o campo e clicar no texto não foca o input |
| palavras coladas | o Astro descarta o espaço antes de tag inline quando há quebra de linha no `.astro` |
| rolagem horizontal / elemento fora da viewport | quebra em mobile (390px) |
| `<img>` sem `alt` | acessibilidade |

O contraste ignora quem tem `background-image` (gradiente não tem uma cor só para
medir) e compõe as camadas translúcidas até achar uma opaca — o `.container` é
`color-mix(..., transparent)` e sozinho não diz nada.

### Antes de auditar, o driver confere o servidor

As rotas saem do `dist/` local, mas o navegador vai no servidor — e nada amarra
os dois. A 4321 é a porta padrão do Astro: qualquer outro projeto da máquina
disputa ela. Com o site institucional servindo ali, a matriz inteira saiu
`✓ 5 rota(s) sem problemas` tendo medido o site errado, com 404 em quatro das
cinco rotas.

Agora o `audit` busca cada rota antes de abrir o navegador e recusa rodar se
alguma não devolver 200:

```
✗ quem atende em http://localhost:4321 não é o frontend "public":
  /acompanhar.html → 404
```

Se a porta estiver tomada, veja de quem é (`ss -ltnp`) e aponte o alvo com
`SITE_URL=http://localhost:4399`. Para trabalho visual isso basta; só volte para
a porta oficial quando precisar da API, que é onde o `ALLOWED_ORIGINS` importa.

### Estado atual: passa limpa

Verificado nas quatro combinações de tema × largura:

| alvo | resultado |
|---|---|
| `public --destravar` | `✓ 5 rota(s) sem problemas` |
| `public` (portões fechados) | `✓ 5 rota(s) sem problemas` |
| `admin --destravar` | `✓ 1 rota(s) sem problemas` |

Achado novo é regressão do commit em questão, não ruído herdado. Os contrastes
que apareciam antes foram corrigidos na origem: `--acao` e `--acao-forte` em
`tokens.css` existem porque o azul e o laranja crus do guia dão 3,12:1 e 2,61:1
sob texto branco. Não os troque pelos hex do guia.

**O que ainda não foi auditado:** `/painel-atendimento.html` redireciona para `/`
sem chave, então a matriz acima o pula. A tela de atendimento — lista de
clientes, tags, linha do tempo — só entra na auditoria com `--admin-key` e a API
no ar. Rode assim depois de mexer no painel.

### Screenshot

```bash
bun .claude/skills/run-site/driver.mjs shot / --out /tmp/shots/index.png
bun .claude/skills/run-site/driver.mjs shot /triagem-suporte.html --destravar --out /tmp/shots/form.png --full
bun .claude/skills/run-site/driver.mjs shot / --projeto admin --admin-key "$CHAVE" --out /tmp/shots/painel.png
```

**Olhe a imagem depois de gerar.** O driver falha alto se o servidor estiver
fora, mas não sabe se o layout ficou certo.

### Inspecionar o DOM

```bash
bun .claude/skills/run-site/driver.mjs eval / "document.title"
bun .claude/skills/run-site/driver.mjs eval / "getComputedStyle(document.body).backgroundColor"
```

Saída verificada do segundo: `"rgb(2, 5, 17)"` — o navy da marca.

| flag | padrão | efeito |
|---|---|---|
| `--projeto` | `public` | qual frontend: define porta padrão e `dist/` |
| `--width` / `--height` | 1440 / 900 | viewport |
| `--theme` | `dark` | grava `data-theme` no `<html>` |
| `--destravar` / `--token` / `--admin-key` | — | abre os portões (ver acima) |
| `--full` | — | página inteira em vez da dobra |
| `--scroll-to <sel>` | — | centraliza o elemento antes de fotografar; falha se não casar |
| `--animate` | — | **não** congela animações |
| `SITE_URL` | pela porta do projeto | servidor alvo |
| `BROWSER_BIN` | auto | caminho do Chromium |

## Run (human path)

```bash
cd frontend
bun run dev:public    # http://localhost:4321
bun run dev:admin     # http://localhost:9080
```

O `astro dev` do Astro 7 **roda como daemon** — retorna na hora e o servidor fica
em segundo plano:

```bash
bunx astro dev status
bunx astro dev logs
bunx astro dev stop
```

## Gotchas

- **A cor computada nem sempre é `rgb()`.** O `.container` usa
  `color-mix(in oklab, …)` e o `getComputedStyle` devolve
  `oklab(0.999 0.00004 0.00002 / 0.6)`. Ler os números com regex tratava `0.999`
  como canal R de 0–255, dava quase-preto, e o tema claro inteiro virava ~30
  falsas falhas de contraste. O driver pinta num canvas 1×1 e relê o pixel — o
  navegador converte qualquer sintaxe.

- **Mas o canvas não é determinístico.** A conversão de perfil de cor varia ±1
  por canal entre execuções: o mesmo `rgb(106,114,133)` volta `107,115,133` numa
  rodada e `106,114,133` na outra, e o contraste do rodapé oscilava entre 4,12 e
  4,19. Por isso `rgb()`/`rgba()` — a esmagadora maioria — é lido com regex
  exata, e o canvas fica só para oklab, lab, `color()` e hsl.

- **Congelar animação vem antes de trocar o tema.** `.btn` e outros têm
  `transition: background .2s`; medir logo depois de gravar o `data-theme` pega a
  cor no meio da transição. A mesma auditoria achava 7 ou 15 problemas conforme a
  máquina estivesse mais ou menos ocupada. Se você mexer na ordem dentro de
  `preparar()`, a auditoria volta a ser um dado ruidoso.

- **`painel-atendimento.html` é uma ponte, não uma página.** Faz
  `location.replace('/')` no `<head>` para não quebrar os e-mails já enviados. O
  contexto de execução morre no meio do `document.fonts.ready` e o CDP responde
  *"Inspected target navigated or closed"*. O driver tolera e a auditoria pula a
  rota com `↷`.

- **`Page.navigate` não rejeita quando a página não carrega.** Ele resolve
  normalmente e põe a falha em `errorText`. Sem checar isso o driver fotografa a
  tela de erro do Chromium e reporta sucesso.

- **Destravar antes do portão assentar não adianta.** O script da triagem decide
  o estado depois do fetch de validação; forçar `#conteudo` visível antes disso é
  desfeito pelo `bloquear()` que chega em seguida. O driver espera
  `#verificando` sumir primeiro.

- **`| tail` mascara o código de saída.** `cmd | tail -3; echo $?` mostra o exit
  do `tail`, sempre 0. Ao verificar se a auditoria falhou, rode sem pipe ou use
  `${PIPESTATUS[0]}`.

- **Sem Chrome nesta máquina.** Só Brave. O symlink usado é
  `/opt/google/chrome/chrome → /opt/brave.com/brave-origin-beta/brave-origin-beta`.
  **Nunca aponte para `/usr/bin/brave-origin-beta`**: é um wrapper que faz
  `exec ".../brave-origin" "$USER_FLAGS" "$BRAVE_FLAGS" "$FLAG" "$@"` e, com as
  variáveis vazias, passa três argumentos vazios ao navegador — o Chromium lê
  como alvos extras e responde `Multiple targets are not supported in headless
  mode`.

- **O driver espera `document.fonts.ready`.** Sem isso o screenshot sai com a
  fonte de fallback e o layout mede diferente do real.

## Troubleshooting

- **`net::ERR_CONNECTION_REFUSED`**: nenhum servidor no ar, ou o `--projeto` não
  bate com a porta. Suba o `preview` como na seção Run.

- **Tudo "Acesso restrito" / só o portão de login na foto**: faltou
  `--destravar`, `--token` ou `--admin-key`.

- **`login de admin falhou: Chave de admin inválida`**: a chave não bate com o
  `ADMIN_KEY` do `.env` que subiu o container.

- **`login de admin falhou: Não foi possível conectar`**: API fora
  (`docker compose up -d`), ou o `PUBLIC_API_BASE` do `frontend/admin/.env`
  aponta para a tailnet em vez de `http://localhost:8000` — e o valor foi embutido
  **no build**, então mudar o `.env` exige rebuildar.

- **`Nenhum Chromium encontrado`**: nenhum dos caminhos padrão existe. Defina
  `BROWSER_BIN=/caminho/do/binario`.

- **`navegador saiu com código 1` + `Multiple targets are not supported`**: o
  binário é o wrapper do Brave, não o lançador. Ver Gotchas.

- **`astro check` falha com "does not expose the programmatic API"**: o
  TypeScript subiu para 7.x. O projeto pina `^6` de propósito — reinstale com
  `bun add -d typescript@^6`.
