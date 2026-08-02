# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

O repositório é escrito em **português** — nomes de função, variáveis, tabelas,
rotas, commits e comentários. Mantenha isso ao escrever código novo. Os
comentários existentes explicam *por que* a decisão foi tomada (geralmente
citando o bug que motivou); siga esse estilo em vez de comentar o óbvio.

## Comandos

### Backend (FastAPI + SQLite, Python 3.14, uv)

```bash
docker compose up -d              # ou: make up
curl http://localhost:8000/health
docker compose logs -f api
make api-restart                  # derruba, sobe e republica a porta no tailscale

cd backend
uv run pytest -q                              # suíte inteira
uv run pytest tests/test_routes.py -q         # um arquivo
uv run pytest tests/test_relatorio_md.py::test_sumario_com_links -q   # um teste
uv run python seed_dados.py                   # popula banco vazio (idempotente)

bun install                                   # só para mexer no schema
bun run generate                              # drizzle/schema.ts → drizzle/migrations/*.sql
```

Não há linter nem formatter configurado no backend.

`bun run generate` **pede TTY**: quando o Drizzle não consegue decidir sozinho se
uma coluna foi renomeada ou trocada, ele pergunta. Rodado por um agente sem
terminal ele trava — quem roda é você. Não force um TTY falso (`script -qec` e
parentes): a resposta errada nessa pergunta gera `DROP COLUMN` + `ADD COLUMN` em
vez de `RENAME COLUMN`, e aí a migração apaga os dados da coluna em silêncio.

### Frontend (dois projetos Astro 7 em workspaces bun)

```bash
cd frontend
bun install
echo 'PUBLIC_API_BASE=http://localhost:8000' | tee public/.env admin/.env

bun run dev:public    # http://localhost:4321
bun run dev:admin     # http://localhost:9080
bun run build         # os dois
bun run build:public  # só o público (é o que a Vercel roda)
bun run check         # astro check nos dois — TypeScript + templates
```

Não existe suíte de testes no frontend: a verificação é `build` + `check`.

As portas 4321 e 9080 importam — `ALLOWED_ORIGINS` no `.env` da API precisa
listar a origem exata, senão o navegador barra por CORS antes da requisição
chegar na API.

## Arquitetura

Você cadastra o cliente e gera um link de uso único → ele preenche o formulário
público (Vercel) → API no Raspberry Pi → você atende pelo painel interno (só na
tailnet) → o cliente acompanha por um código, como rastreio de encomenda → sai
PDF de orçamento e/ou relatório técnico em Markdown.

### O cliente é pasta, não cópia

`clientes` é a raiz: e-mail único e normalizado. Token, triagens, execução e
histórico penduram nele por `cliente_id`, com `ON DELETE CASCADE`. As triagens
**não** guardam mais nome, e-mail e telefone — era o que fazia o mesmo cliente
existir três vezes com três grafias do próprio nome.

Quem decide de quem é a triagem é o `cliente_id` gravado no **token**, nunca o
que foi digitado na tela. Por isso o mesmo cliente abre quantos atendimentos
quiser, em serviços diferentes, sem colidir — e um erro de digitação não cria
pasta fantasma.

### Estado derivado, nunca guardado

O estado do atendimento é **o título do último evento visível** de `historico`
(`app/historico.py::estado_atual`, e a subquery `ESTADO_ATUAL` em
`routers/admin.py`). Não existe coluna `status` em `execucao` — ela foi removida
de propósito.

Guardar uma cópia foi exatamente o que produziu os bugs desta base: um caminho
gravava o evento e não o status, e o cliente via o atendimento parado enquanto
ele andava. Sem cópia não há divergência, e apagar um evento devolve o estado
anterior sozinho.

**Não há lista de etapas predefinida.** Quem escreve o título de cada passo é
você, na hora; as sugestões (`/admin/titulos`) vêm do que já foi usado antes —
aprendidas, não decretadas. Sete passos fixos prometiam um caminho que nem sempre
existe: projeto de desenvolvimento não espera peça nenhuma. Ao mexer aqui, não
reintroduza vocabulário fixo.

### Dois níveis de exposição — a separação é o ponto do projeto

- `frontend/public/` → **Vercel**, internet aberta. API exposta por `tailscale funnel`.
- `frontend/admin/` → **nunca** vai para a Vercel. Servido por `tailscale serve`, só dentro da tailnet.

São dois projetos Astro separados justamente porque um `dist/` único faria
publicar o formulário publicar o painel junto. O `vercel.json` na raiz fixa
`outputDirectory: frontend/public/dist` e o build entra em `frontend/` (não em
`frontend/public/`) porque `@nlc/shared` é workspace do bun. Ao mexer em deploy,
não troque `serve` por `funnel` no alvo do painel.

### Acoplamentos que quebram em silêncio

1. **Campos de triagem ↔ colunas do SQLite.** `frontend/shared/lib/triagem.ts`
   define os campos; os `nome` batem 1:1 com as colunas de `triagem_suporte` /
   `triagem_seguranca` / `triagem_desenvolvimento` em `backend/drizzle/schema.ts`.
   O INSERT é montado a partir das chaves do modelo Pydantic
   (`app/routers/triagem.py::_registrar_triagem`), então renomear de um lado só
   quebra sem erro claro. O painel também lê esses rótulos — há uma única lista.

   A exceção é o bloco de contato: `nome` e `telefone` são retirados do payload
   (`CAMPOS_DE_CONTATO`) e atualizam a ficha do cliente em vez de virarem coluna.

2. **Schema no Drizzle, migração em Python.** `backend/drizzle/schema.ts` é a
   fonte da verdade. `bun run generate` compara com o histórico e escreve um
   `.sql` numerado em `drizzle/migrations/` — versionado no git. Quem aplica é
   `app/migrar.py`, no boot, com o `sqlite3` da stdlib: assim o Pi não precisa de
   Node nem bun para subir a API.

   A consequência a não esquecer: **as consultas continuam em SQL puro no
   Python**. Renomear uma coluna no `schema.ts` gera a migração certa e não
   reescreve nenhum SELECT. O Drizzle aqui é ferramenta de autoria, não ORM.

   `app/migrar.py` é idempotente (tabela de controle `_migracoes`), corta os
   comandos em `--> statement-breakpoint` e roda cada arquivo na sua própria
   transação — falha no meio volta atrás e não registra a tag.

3. **Métodos HTTP no CORS.** `allow_methods` em `app/__init__.py` lista os verbos
   um a um. Ficou em `GET/POST/OPTIONS` enquanto o painel já chamava PUT e
   DELETE: o navegador barrava no *preflight* e a ação não acontecia, **sem erro
   na tela**. Rota nova com verbo novo pede a entrada aqui.

   Isto não aparece no `curl` — ele não faz preflight. Mudança de escrita se
   verifica pelo navegador (a skill `run-site`), não por `curl`.

4. **URLs `.html`.** Ambos os `astro.config.mjs` usam `build.format: 'file'`.
   Mudar para o padrão `directory` transforma `/triagem-suporte.html` em
   `/triagem-suporte/` e quebra todo link de token já enviado a cliente.

### Identidade visual dos PDFs

`backend/marca/` é fonte única de cores, fontes (Poppins/Inter versionadas em
`marca/fontes/`), estilos e template de página A4. Tanto `pdf_relatorio.py`
(orçamento/O.S.) quanto `relatorio_md.py` (relatório técnico) importam de lá —
não recrie paleta local. Os valores vêm de `guia-marca.md`.

O banco guarda o **Markdown**, não o PDF: o documento é montado a cada download,
para que relatório antigo saia no template atual. `docs/relatorio-exemplo.md` é a
referência viva de todos os estilos — se um bloco sair diferente, é regressão.

Imagens de relatório vêm de `backend/relatorios_imagens/` e a arte da capa de
`backend/marca/arte/capa.png`; ambos são **volumes montados**, então trocar
arquivo ali vale no próximo PDF sem rebuild. Imagens por URL não são baixadas de
propósito (SSRF).

### Segurança — decisões deliberadas, não descuido

- Chave de admin vive **só em memória** (`frontend/shared/lib/admin.ts`); nada de
  `localStorage`. Recarregar desloga. Não "conserte" isso.
- Não há rota de login: autenticar é fazer uma chamada autenticada barata
  (`/admin/catalogo`) e ver se volta 401.
- `checar_admin` usa `secrets.compare_digest` (tempo constante).
- Token de triagem é de uso único: validação + INSERT + consumo num único commit,
  e o `UPDATE ... AND usado = 0` fecha a corrida entre duas requisições
  simultâneas.
- Rate limit em memória por IP + rota; o container roda com `--proxy-headers`
  porque atrás do Funnel o IP real chega no `X-Forwarded-For`.
- `execucao.observacoes_internas` nunca aparece em PDF nem na página do cliente;
  `clientes.notas` também não.
- **O acompanhamento é aberto pelo código, e só.** `/acompanhar/{codigo}` não
  pede senha — o código é o segredo, como no rastreio dos Correios. Por isso a
  resposta é *curada* (`routers/acompanhar.py`), não o dump da triagem: sai o
  estado, a linha do tempo visível e o contato. Não acrescente campo ali sem
  perguntar se ele pode ser lido por quem achar o código.
- Evento com `visivel_cliente = 0` fica só no seu histórico. É o que permite
  anotar sem publicar.
- O cliente pode corrigir contato e mandar recado pelo acompanhamento, mas
  **não** trocar o e-mail: e-mail é a identidade da pasta, e deixá-lo editável
  por quem tem o código seria mover atendimento de pasta sem autenticação.

### Configuração e tempo

`backend/app/config.py` (pydantic-settings) valida no boot: faltando variável
obrigatória (`ALLOWED_ORIGINS`, `ADMIN_KEY`, `PAINEL_BASE_URL`), a API não sobe e
lista todas de uma vez. O `compose.yml` repassa o `.env` inteiro via `env_file` —
variável nova exige editar só o `.env`.

Datas: `app/tempo.py` grava UTC **naive** (compatível com linhas antigas) e
converte para America/São_Paulo só na exibição. Não introduza `datetime` aware no
banco.

Testes: `backend/tests/conftest.py` define as variáveis de ambiente *antes* de
`app.config` ser importado e aponta `DB_PATH` para um tempdir — a suíte nunca
toca no banco real. Variável de ambiente vence o `.env` no pydantic-settings.

## Verificação visual

`.claude/skills/run-site/` dirige os dois frontends num Chromium headless (CDP
direto, sem Playwright) e audita as páginas renderizadas: contraste WCAG nos dois
temas, portão de acesso, campo sem rótulo, layout em 390px. Leia o SKILL.md antes
de usar — sem abrir os portões (`--destravar`, `--token` ou `--admin-key`) a
auditoria enxerga só a tela de bloqueio.

A auditoria é determinística; número diferente entre duas rodadas iguais é bug do
driver, não flutuação. Hoje ela **passa limpa** nos dois projetos com
`--destravar`, nas quatro combinações de tema × largura — então achado novo é
regressão do seu commit, não ruído herdado.

O driver confere antes de auditar que quem atende em `SITE_URL` é mesmo aquele
frontend. A 4321 é a porta padrão do Astro e qualquer outro projeto da máquina
disputa ela; sem essa checagem a matriz inteira sai verde tendo medido o site
errado, com 404 nas rotas que não existem lá. Já aconteceu.
