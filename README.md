# nlc-forms

Sistema de triagem, atendimento e relatório de clientes — NextLevelCode.

O cliente recebe um link de uso único, preenche a triagem e ganha um código de
acompanhamento. Você atende pelo painel, monta o orçamento, gera o PDF e — se o
caso pedir — escreve um relatório técnico em Markdown que sai no template da
marca.

Tudo roda em infraestrutura própria: a API e o painel ficam no Raspberry Pi, e só
os formulários públicos são hospedados fora.

## Estrutura

```
nlc-forms/
├── backend/
│   ├── app/                   # FastAPI modular
│   │   ├── config.py          #   Settings (pydantic-settings) — valida no boot
│   │   ├── tempo.py           #   Datas em UTC + conversão para Brasília
│   │   ├── database.py        #   SQLite — init, seed, get_db
│   │   ├── models.py          #   Modelos Pydantic
│   │   ├── auth.py            #   Tokens, admin key, validação
│   │   ├── notify.py          #   Notificação por e-mail (SMTP)
│   │   ├── ratelimit.py       #   Rate limiter em memória
│   │   └── routers/           #   admin, triagem, consulta, token, health
│   ├── marca/                 # Identidade visual dos PDFs — fonte única
│   │   ├── cores.py           #   Paleta do guia-marca.md
│   │   ├── fontes.py          #   Registro de Poppins/Inter no reportlab
│   │   ├── fontes/*.ttf       #   Fontes versionadas (OFL)
│   │   ├── estilos.py         #   Fábrica de ParagraphStyle
│   │   ├── template.py        #   Página A4: capa, cabeçalho, rodapé "N/M"
│   │   └── arte/              #   capa.png (montada no container) + CAPA.md
│   ├── pdf_relatorio.py       # PDF de orçamento/O.S.
│   ├── relatorio_md.py        # Markdown → PDF no template da marca
│   ├── relatorios_imagens/    # Imagens citadas nos relatórios (montada)
│   ├── seed_dados.py          # 3 clientes fictícios — só com SEED_DEMO=true
│   ├── tests/                 # pytest (conftest.py isola o ambiente)
│   └── Dockerfile
├── frontend/                  # Monorepo Astro (bun workspaces)
│   ├── shared/                # Comum aos dois — nunca vira site sozinho
│   │   ├── lib/               #   api.ts, admin.ts, triagem.ts
│   │   ├── styles/            #   tokens.css, base.css
│   │   └── components/        #   Cabecalho, Rodape
│   ├── public/                # Formulários públicos → Vercel
│   │   └── src/pages/         #   index + 3 triagens (URLs .html preservadas)
│   └── admin/                 # Painel interno → só na tailnet
│       └── src/               #   app de página única: lista, atendimento, token
├── docs/
│   ├── arquitetura.puml       # Diagrama da arquitetura
│   ├── db.puml                # Diagrama das tabelas
│   ├── relatorio-exemplo.md   # Referência de todos os estilos do relatório
│   └── img-examples/          # Referência visual do PDF (capa, sumário, corpo)
├── compose.yml                # API + volumes
├── vercel.json                # Build do público (só ele) na Vercel
├── .env.example               # Template de configuração
├── Makefile                   # Atalhos (docker, tailscale, front)
├── backup.sh / restore.sh     # Backup .7z criptografado + restauração
└── guia-marca.md              # Cores, tipografia e uso da marca
```

## Arquitetura

```
   Cliente (internet)                        Você (tailnet)
          │                                        │
          ▼                                        ▼
  ┌────────────────┐                     ┌────────────────────┐
  │     Vercel     │                     │  frontend/admin    │
  │ frontend/public│                     │  tailscale serve   │
  │  (só HTML/JS)  │                     │  (não sai da rede) │
  └───────┬────────┘                     └─────────┬──────────┘
          │ POST /triagem/{servico}?token=         │ X-Admin-Key
          ▼                                        ▼
       ┌──────────────────────────────────────────────────┐
       │            Raspberry Pi (sua casa)               │
       │   FastAPI + SQLite  ·  Docker  ·  reportlab      │
       │   /triagem/*, /token/*, /consulta   → público    │
       │   /admin/*                          → admin key  │
       │   exposto por Tailscale Funnel na porta 8000     │
       └───────────────────────┬──────────────────────────┘
                               │
                 ┌─────────────┴─────────────┐
                 ▼                           ▼
        ┌──────────────────┐       ┌──────────────────┐
        │ Backup externo 1 │       │ Backup externo 2 │
        │ .7z criptografado│       │ .7z criptografado│
        └──────────────────┘       └──────────────────┘
```

O painel **nunca** vai para a Vercel. É por isso que `public/` e `admin/` são dois
projetos Astro separados, com builds independentes: com um `dist/` único, publicar
o formulário publicaria o painel junto — e um erro de configuração bastaria para
expor a tela que lê os dados dos clientes.

Diagramas completos em [`docs/arquitetura.puml`](docs/arquitetura.puml) e
[`docs/db.puml`](docs/db.puml).

## Fluxo completo

```
1. Cliente conversa com você no WhatsApp
2. Você abre o painel → aba "Gerar token" → gera um link de acesso único
3. Manda o link para o cliente
4. Cliente abre, preenche a triagem, recebe um código (NLC-XXXX-XXXX)
5. Você recebe um e-mail de notificação (se SMTP configurado)
6. O e-mail leva direto ao cliente no painel; ou você busca pelo código na lista
7. Preenche diagnóstico, serviços realizados, recomendações e itens de orçamento
8. Gera o PDF de orçamento — ou envia por e-mail direto do painel
9. Se o caso pedir, escreve um relatório técnico em Markdown e baixa o PDF
```

A chave de admin é digitada **uma vez por sessão** e vive só em memória: nunca vai
para `localStorage` nem para o disco. Recarregar a página desloga, de propósito.

## Rodar localmente

### API

```bash
cp .env.example .env      # ajuste ADMIN_KEY antes de subir
docker compose up -d
curl http://localhost:8000/health     # → {"status":"ok"}
```

Documentação interativa em <http://localhost:8000/docs>.

### Frontends

Os dois projetos leem o endereço da API de `PUBLIC_API_BASE`. O prefixo `PUBLIC_`
é do Astro: só variáveis com ele entram no JS que roda no navegador — exatamente o
certo para um endereço, e exatamente o errado para a chave de admin.

```bash
cd frontend
bun install

# Endereço da API em desenvolvimento (o .env é ignorado pelo git)
echo 'PUBLIC_API_BASE=http://localhost:8000' | tee public/.env admin/.env

bun run dev:public    # http://localhost:4321
bun run dev:admin     # http://localhost:9080
```

> As portas importam: o `ALLOWED_ORIGINS` do `.env` da API precisa listar a origem
> exata do frontend, senão o navegador barra a requisição por CORS antes mesmo de
> ela chegar na API. As portas 4321 e 9080 já vêm liberadas no `.env.example`.

Outros comandos:

```bash
bun run build     # constrói os dois
bun run check     # astro check (TypeScript + templates) nos dois
```

## Configuração

Todas as variáveis são lidas do ambiente via `.env`. A configuração é validada no
boot por um modelo `pydantic-settings` (`backend/app/config.py`): se faltar alguma
obrigatória, a API não sobe e o erro lista **todas** as que faltam de uma vez.

| Variável | Padrão | Descrição |
|---|---|---|
| `ALLOWED_ORIGINS` | **obrigatória** | Origens permitidas no CORS, separadas por vírgula |
| `ADMIN_KEY` | **obrigatória** | Chave do painel — gere com `openssl rand -base64 32` |
| `PAINEL_BASE_URL` | **obrigatória** | URL base do painel (usada no link do e-mail) |
| `DB_PATH` | `/data/forms.db` | Caminho do SQLite |
| `TOKEN_TTL_HOURS` | `48` | Validade padrão dos links de triagem |
| `SMTP_HOST` | vazio | Servidor SMTP (vazio = sem notificações) |
| `SMTP_PORT` | `587` | Porta SMTP |
| `SMTP_USER` | vazio | Usuário do SMTP |
| `SMTP_PASS` | vazio | Senha do SMTP |
| `SMTP_FROM` | (= `SMTP_USER`) | Remetente do e-mail |
| `NOTIFY_TO` | vazio | Seu e-mail (recebe notificação de nova triagem) |
| `RATE_LIMIT` | `10` | Requisições por janela (por IP + rota) |
| `RATE_LIMIT_WINDOW` | `60` | Janela do rate limit, em segundos |
| `SEED_DEMO` | `false` | `true` popula banco vazio com clientes fictícios |

O `compose.yml` repassa o `.env` inteiro com `env_file`, então adicionar uma
variável nova exige editar só o `.env` — não os dois arquivos.

No frontend a única variável é `PUBLIC_API_BASE`, em `frontend/public/.env` e
`frontend/admin/.env` (ou nas variáveis de ambiente da Vercel).

## Relatório técnico em Markdown

Além do PDF de orçamento, o painel gera um **relatório longo** a partir de
Markdown, sempre no mesmo template da marca.

O que fica guardado no banco é o **Markdown**, não o PDF. O documento é montado a
cada download — assim, quando o template muda, todo relatório antigo passa a sair
no template novo. Guardar o binário congelaria o histórico numa versão velha da
identidade visual.

O renderizador entende títulos (numerados automaticamente), sumário com links,
listas aninhadas, tabelas, citações, blocos de código, imagens locais e marcação
inline. A referência viva de todos os estilos é
[`docs/relatorio-exemplo.md`](docs/relatorio-exemplo.md): suba esse arquivo pelo
painel, gere o PDF e compare — se algum bloco sair diferente, é regressão.

Imagens vêm de `backend/relatorios_imagens/` (montada no container, então soltar
um `.png` ali já vale no próximo PDF). Imagens por URL **não** são baixadas: o
servidor buscar um endereço vindo de campo de texto é SSRF.

### Capa

Se existir `backend/marca/arte/capa.png`, ela vira a primeira página. Sem o
arquivo, o documento abre direto no sumário — nenhuma capa é inventada.

A arte é exportada do Canva **sem** os textos que mudam; título, subtítulo,
descrição, autores, data e código são escritos por cima na hora, com as fontes da
marca — texto de verdade, selecionável e nítido em qualquer zoom. As posições
estão em `CAPA_LAYOUT` (`backend/relatorio_md.py`) e o passo a passo em
[`backend/marca/arte/CAPA.md`](backend/marca/arte/CAPA.md).

## Testes

```bash
cd backend
uv run pytest -q
```

As variáveis de ambiente dos testes ficam em `tests/conftest.py`, que também
aponta o `DB_PATH` para um diretório temporário — rodar a suíte nunca toca no
banco real.

## Deploy no Raspberry Pi

O Pi hospeda a API (pública, via Funnel) e o painel (privado, via Serve). São dois
níveis de exposição diferentes, e o comando de cada um é diferente — não troque.

### 1. Levar o projeto para o Pi

```bash
rsync -av --exclude node_modules --exclude dist --exclude .env \
      nlc-forms/ pi@<nome-do-pi>:~/nlc-forms/
```

Ou clone do Git direto no Pi, se o repositório estiver hospedado.

### 2. Configurar

```bash
cd ~/nlc-forms
cp .env.example .env
openssl rand -base64 32        # cole o resultado em ADMIN_KEY
nano .env
```

No `.env` de produção, três valores mudam em relação ao local:

```bash
ALLOWED_ORIGINS=https://support.nextlevelcode.pro,https://<pi>.<tailnet>.ts.net:9080
PAINEL_BASE_URL=https://<pi>.<tailnet>.ts.net:9080
SEED_DEMO=false
```

`ALLOWED_ORIGINS` precisa conter o domínio da Vercel — é de lá que o navegador do
cliente chama a API.

### 3. Subir a API

```bash
docker compose up -d --build     # ou: make up
curl http://localhost:8000/health
```

A imagem é `python:3.14-slim` e o `uv sync --frozen` instala as versões travadas
do `uv.lock`, então o build é reprodutível. O container roda com `--proxy-headers`
porque atrás do Funnel o IP real chega no `X-Forwarded-For` — sem isso o rate
limit trataria o mundo inteiro como um cliente só.

### 4. Expor a API com Tailscale Funnel

```bash
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up
tailscale funnel --bg --https=8000 http://127.0.0.1:8000
tailscale funnel status
```

**Funnel** e não **Serve**: o formulário roda no navegador do cliente, que está na
internet e não na sua tailnet. A URL sai como
`https://<nome-do-pi>.<tailnet>.ts.net:8000` — é ela que vai no `PUBLIC_API_BASE`
da Vercel.

### 5. Servir o painel só na tailnet

Antes de buildar, aponte o painel para a API:

```bash
echo 'PUBLIC_API_BASE=https://<pi>.<tailnet>.ts.net:8000' > frontend/admin/.env
make front-on
```

O alvo faz `bun install`, `bun run build:admin`, serve o `dist/` em
`127.0.0.1:9080` e publica com `tailscale serve --https=9080`. Aqui é **Serve**
mesmo: quem abre o painel é você, de dentro da tailnet. Pôr o painel em Funnel o
exporia à internet inteira, com só a chave de admin no caminho.

Para derrubar: `make front-server-off`.

### 6. Atualizar depois

```bash
git pull                # ou rsync de novo
make api-restart        # derruba, sobe e republica a porta 8000
make front-on           # rebuilda e republica o painel
```

> `make api-restart` usa `tailscale serve` para desligar e religar a porta 8000.
> Se a API está em Funnel, troque `serve` por `funnel` nessas duas linhas do
> Makefile — senão o religamento rebaixa a API para a tailnet e os formulários
> param de responder.

Trocar a arte da capa ou soltar imagens de relatório **não** pede rebuild:
`backend/marca/arte/` e `backend/relatorios_imagens/` são volumes montados.

## Deploy dos formulários na Vercel

Só `frontend/public/` vai para a Vercel. O `vercel.json` na raiz já fixa isso:

```json
{
  "buildCommand": "cd frontend && bun install --frozen-lockfile && bun run build:public",
  "outputDirectory": "frontend/public/dist",
  "framework": null
}
```

O build entra em `frontend/` e não em `frontend/public/` porque o `@nlc/shared` é
um workspace do bun: instalando de dentro do projeto público, a dependência não
resolve. E o `outputDirectory` aponta só para `public/dist`, então não existe
caminho pelo qual o painel chegue à Vercel.

### Pelo GitHub (recomendado)

1. Suba o repositório no GitHub.
2. Em [vercel.com/new](https://vercel.com/new), importe o repositório.
3. **Root Directory: deixe na raiz** — quem manda é o `vercel.json`.
4. Em *Settings → Environment Variables*, crie:

   ```
   PUBLIC_API_BASE = https://<nome-do-pi>.<tailnet>.ts.net:8000
   ```

   Ela é lida **no build**, não em tempo de execução: mudou o endereço, precisa de
   um novo deploy para valer.
5. Deploy. Cada push na branch principal republica.

### Pela CLI

```bash
npm i -g vercel        # a CLI não vem instalada
vercel link            # uma vez, na raiz do repositório
vercel env add PUBLIC_API_BASE production
vercel --prod
```

### Conferir antes de publicar

```bash
cd frontend
PUBLIC_API_BASE=https://<pi>.<tailnet>.ts.net:8000 bun run build:public
grep -rl 'ts.net' public/dist/*.html     # o endereço tem que estar embutido
```

As URLs terminam em `.html` de propósito (`build.format: 'file'` no
`astro.config.mjs`): `/triagem-suporte.html` continua existindo. Com o padrão do
Astro elas virariam `/triagem-suporte/` e **todo link de token já enviado a
cliente quebraria**.

As fontes são baixadas no build pela Fonts API do Astro e servidas do próprio
domínio — nenhuma requisição do visitante vai para o Google.

## Dados de exemplo

Com `SEED_DEMO=true` no `.env`, o `seed_dados.py` popula um banco vazio com 3
clientes fictícios (um de cada serviço), com triagem, execução e itens de
orçamento preenchidos — úteis para testar o fluxo inteiro.

**Em produção deixe `SEED_DEMO=false`** (o padrão), senão os fictícios entram no
banco real.

| Serviço | Cliente | Problema | Valor |
|---|---|---|---|
| Suporte | Fábio Rocha | Notebook Lenovo Legion superaquecendo | R$ 450,00 |
| Segurança | Dona Lúcia Silva | WhatsApp clonado (golpe do código SMS) | R$ 280,00 |
| Desenvolvimento | Rafael Santos | Sistema de gestão de OS para MEI | R$ 4.600,00 |

Para rodar manualmente (idempotente — só insere se o banco estiver vazio):

```bash
cd backend && uv run python seed_dados.py
```

## Backup e restauração

`backup.sh` e `restore.sh` operam sobre o container — não precisam parar a API.

```bash
./backup.sh
```

1. Gera uma cópia binária do SQLite (`.db`) dentro do container
2. Exporta todas as tabelas para `.json`
3. Compacta os dois num **`.7z` criptografado** e apaga os arquivos soltos
4. Envia para um host remoto via rsync (se configurado)
5. Mantém os **últimos 7**, apaga os mais antigos

Configure `ZIP_PASSWORD` no topo de `backup.sh` **e** de `restore.sh` (a mesma
senha), e `REMOTE_HOST` / `REMOTE_DIR` / `SSH_KEY` para o envio remoto.

Agendar diariamente às 3h:

```bash
crontab -e
# 0 3 * * * /home/pi/nlc-forms/backup.sh >> /home/pi/nlc-forms/backup.log 2>&1
```

Restaurar:

```bash
./restore.sh --list
./restore.sh backups/forms_2026-06-21_030000.7z
```

O script salva o estado atual antes de sobrescrever (`pre_restore_<timestamp>.db`),
então dá para voltar atrás se restaurar o backup errado.

## Acessar os dados diretamente

```bash
docker cp nlc-forms-api:/data/forms.db ./forms.db
```

Abra com [DB Browser for SQLite](https://sqlitebrowser.org/) para consultar ou
exportar CSV. Os dados moram no volume `nlc-forms_forms_data`.

## Banco de dados

Sem ORM e sem migração: o schema é criado com `CREATE TABLE IF NOT EXISTS` no boot
(`backend/app/database.py`). Isso significa que **coluna nova não alcança banco que
já existe** — mudança de schema em produção pede `ALTER TABLE` na mão.

| Tabela | O que guarda |
|---|---|
| `tokens` | Links de acesso único: `servico`, `expira_em`, `usado`, `nota` |
| `triagem_suporte` | Respostas do formulário de suporte |
| `triagem_seguranca` | Respostas do formulário de segurança |
| `triagem_desenvolvimento` | Respostas do formulário de dev |
| `catalogo_itens` | Itens de orçamento com preço sugerido por serviço |
| `execucao` | O atendimento: diagnóstico, serviços, recomendações, itens, total |
| `relatorios_md` | Relatórios técnicos: o Markdown e os metadados da capa |

Toda triagem tem `codigo` (NLC-XXXX-XXXX) e o `token` usado no acesso.
`execucao.observacoes_internas` não aparece em PDF nenhum.

## Endpoints

| Método | Rota | Uso |
|---|---|---|
| GET | `/health` | Verificação de status |
| GET | `/token/{token}/validar` | O formulário valida o token antes de aparecer |
| POST | `/triagem/suporte` | Cliente envia a triagem de suporte |
| POST | `/triagem/seguranca` | Cliente envia a triagem de segurança |
| POST | `/triagem/desenvolvimento` | Cliente envia a triagem de dev |
| GET | `/consulta?codigo=X` | Consulta pública por código |
| GET | `/consulta?email=X` | Consulta por e-mail (requer admin) |
| POST | `/admin/gerar-token` | Gera link de triagem |
| GET | `/admin/triagens` | Lista com filtros e paginação |
| GET | `/admin/triagem/{codigo}` | Triagem + execução de um cliente |
| GET | `/admin/catalogo?servico=X` | Itens do catálogo |
| POST | `/admin/execucao` | Salva o atendimento |
| GET | `/admin/relatorio/{codigo}.pdf` | PDF de orçamento |
| POST | `/admin/enviar-pdf` | Envia o PDF por e-mail ao cliente |
| POST | `/admin/relatorios-md` | Cria relatório técnico |
| GET | `/admin/relatorios-md?codigo=` | Lista relatórios (sem o Markdown) |
| GET | `/admin/relatorios-md/{id}` | Devolve o Markdown para reabrir no editor |
| PUT | `/admin/relatorios-md/{id}` | Atualiza |
| DELETE | `/admin/relatorios-md/{id}` | Remove |
| GET | `/admin/relatorios-md/{id}.pdf` | Renderiza o PDF na hora |

Tudo sob `/admin/` exige o header `X-Admin-Key`.
