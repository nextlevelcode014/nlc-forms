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
```

Não há linter nem formatter configurado no backend.

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

Cliente preenche um formulário público (Vercel) → API no Raspberry Pi → você
atende pelo painel interno (só na tailnet) → gera PDF de orçamento e/ou
relatório técnico em Markdown.

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
   `triagem_seguranca` / `triagem_desenvolvimento` em `backend/app/database.py`.
   O INSERT é montado a partir das chaves do modelo Pydantic
   (`app/routers/triagem.py::_registrar_triagem`), então renomear de um lado só
   quebra sem erro claro. O painel também lê esses rótulos — há uma única lista.

2. **Schema sem ORM e sem migração.** As tabelas nascem de
   `CREATE TABLE IF NOT EXISTS` no boot. Coluna nova **não** alcança banco
   existente: mudança de schema em produção pede `ALTER TABLE` manual.

3. **URLs `.html`.** Ambos os `astro.config.mjs` usam `build.format: 'file'`.
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
- `execucao.observacoes_internas` nunca aparece em PDF.

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
driver, não flutuação. Ela **não passa limpa hoje** — os achados abertos estão
listados no SKILL.md.
