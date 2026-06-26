# nlc-forms

Sistema de triagem, atendimento e relatório de clientes — NextLevelCode.

## Estrutura

```
nlc-forms/
├── backend/
│   ├── app/                  # FastAPI modular (config, database, auth, routers…)
│   │   ├── config.py         #   Variáveis de ambiente
│   │   ├── database.py       #   SQLite — init, seed, get_db
│   │   ├── models.py         #   Pydantic models
│   │   ├── auth.py           #   Tokens, admin key, validação
│   │   ├── notify.py         #   Notificação por e-mail (SMTP)
│   │   ├── ratelimit.py      #   Rate limiter em memória
│   │   └── routers/          #   admin, triagem, consulta, token, health
│   ├── pdf_relatorio.py      # Geração do PDF final (reportlab)
│   ├── seed_dados.py         # Popula banco com 3 clientes fictícios (1 por serviço)
│   ├── pyproject.toml
│   └── Dockerfile
├── frontend/
│   ├── public/                      # Formulários públicos (deploy na web)
│   │   ├── triagem-suporte.html
│   │   ├── triagem-seguranca.html
│   │   ├── triagem-desenvolvimento.html
│   │   └── logo.png
│   └── admin/                       # Painel interno (só local)
│       ├── admin-gerar-token.html
│       ├── admin-lista-clientes.html
│       ├── painel-atendimento.html
│       └── logo.png
├── docs/
│   └── arquitetura.puml     # Diagrama PlantUML da arquitetura
├── compose.yml               # Docker Compose com env vars
├── .env.example              # Template de configuração (commitado)
├── .env                      # Configuração real (ignorado pelo git)
├── Makefile                  # Comandos rápidos (docker, tailscale, front local)
├── backup.sh                 # Backup .db + .json → .7z criptografado, envio remoto
├── restore.sh                # Restaura a partir de .db ou .7z
└── diagrama.puml             # Diagrama PlantUML das tabelas do banco
```

## Arquitetura

```
                        ┌──────────────────┐
                        │     Vercel       │
                        │  frontend/public │ ◄── Cliente (URL com token)
                        └────────┬─────────┘
                                 │ POST /triagem/{servico}?token=
                                 ▼
                   ┌─────────────────────────┐
                   │  Servidor Casa          │
                   │  (Tailscale Funnel)     │
                   │  FastAPI + SQLite       │
                   │  /triagem/*  (público)  │
                   │  /admin/*   (privado)   │
                   └────────┬─────────┬──────┘
                            │         │
                            ▼         ▼
            ┌──────────────────┐   ┌──────────────────┐
            │ Backup Externo 1 │   │ Backup Externo 2 │
            │ .7z criptografado│   │ .7z criptografado│
            └──────────────────┘   └──────────────────┘

  ┌──────────────────┐
  │  Rede Privada    │
  │  frontend/admin/ │ ◄── Admin
  │  (Tailscale)     │
  └──────────────────┘
```

Diagrama completo (PlantUML) em [`docs/arquitetura.puml`](docs/arquitetura.puml).

## Fluxo completo

```
1. Cliente conversa com você no WhatsApp
2. Você abre admin-gerar-token.html, gera um link de acesso único
3. Manda o link pro cliente
4. Cliente abre o link, preenche a triagem, recebe um código (NLC-XXXX-XXXX)
5. Você recebe um e-mail de notificação (se SMTP configurado)
6. Você abre painel-atendimento.html, busca pelo código (ou admin-lista-clientes.html para ver todas as triagens com filtros)
7. Preenche diagnóstico, serviços realizados, recomendações e itens de orçamento
8. Gera o PDF final — documento pronto para enviar ao cliente
```

## Dados de exemplo

Na primeira inicialização, o `seed_dados.py` popula automaticamente o banco com 3 clientes fictícios (um de cada serviço) com triagem, execução e itens de orçamento preenchidos — úteis para testar a geração de PDF e o fluxo completo.

Os dados atuais:

| Serviço | Cliente | Problema | Valor |
|---|---|---|---|
| Suporte | Fábio Rocha | Notebook Lenovo Legion superaquecendo | R$ 450,00 |
| Segurança | Dona Lúcia Silva | WhatsApp clonado (golpe do código SMS) | R$ 280,00 |
| Desenvolvimento | Rafael Santos | Sistema de gestão de OS para MEI | R$ 4.600,00 |

Para rodar manualmente:

```bash
cd backend
uv run python seed_dados.py
```

Só insere dados se o banco estiver vazio (idempotente).

## Testar localmente (WSL / Linux)

```bash
# Subir a API
docker compose up -d

# Verificar se está rodando
curl http://localhost:8000/health
# → {"status":"ok"}
```

Pasta `public/` vai pra Vercel (domínio público separado).

Pasta `admin/` serve localmente:

```bash
nohup python3 -m http.server 9080 -d frontend/admin > server.log 2>&1 &
```

Exponha na tailnet com Tailscale Serve:

```bash
tailscale serve --bg http://localhost:9080
```

Acesse pelo domínio tailnet da máquina (ex: `https://admin.tailXXXXX.ts.net`).

## Configuração

Todas as variáveis são lidas do ambiente via `.env`. Copie `.env.example` para `.env` e ajuste:

```bash
cp .env.example .env
```

| Variável | Padrão | Descrição |
|---|---|---|
| `ALLOWED_ORIGINS` | `http://localhost:3000,…` | Domínios permitidos (CORS) |
| `ADMIN_KEY` | `troque-essa-chave` | Chave do painel — **troque em produção** |
| `TOKEN_TTL_HOURS` | `48` | Validade padrão dos links de triagem |
| `SMTP_HOST` | vazio | Servidor SMTP (vazio = sem notificações) |
| `SMTP_PORT` | `587` | Porta SMTP |
| `SMTP_USER` | vazio | Usuário do SMTP |
| `SMTP_PASS` | vazio | Senha do SMTP |
| `SMTP_FROM` | (= SMTP_USER) | Remetente do e-mail |
| `NOTIFY_TO` | vazio | Seu e-mail (recebe notificações) |
| `PAINEL_BASE_URL` | obrigatória | URL base do admin (link do e-mail) |
| `RATE_LIMIT` | `10` | Requisições por janela (por IP) |
| `RATE_LIMIT_WINDOW` | `60` | Janela do rate limit em segundos |

## Produção no Raspberry Pi

### 1. Copiar o projeto para o Pi

```bash
scp -r nlc-forms/ pi@<ip-do-pi>:~/
```

### 2. Configurar via .env

```bash
cp .env.example .env
# Edite .env com seus valores de produção
```

### 3. Subir no Pi

```bash
cd ~/nlc-forms
docker compose up -d --build
```

### 4. Expor com Tailscale Funnel

```bash
curl -fsSL https://tailscale.com/install.sh | sh
tailscale funnel 8000
```

Vai gerar uma URL pública tipo `https://<nome-do-pi>.tail12345.ts.net`.

### 5. Deploy dos formulários públicos

Faça deploy da pasta `frontend/public/` na Vercel.

**Via CLI:**

```bash
cd frontend/public
npx vercel --prod
```

**Via GitHub (recomendado):**
1. Push o repositório no GitHub
2. Acesse [vercel.com/new](https://vercel.com/new)
3. Importe o repositório, ajuste **Root Directory** para `frontend/public`
4. Deploy

Antes do deploy, troque a `API_BASE` nos 3 arquivos de `public/`:
```javascript
const API_BASE = "https://<seu-dominio-api>";
```

Os arquivos em `admin/` (`admin-gerar-token.html`, `painel-atendimento.html`) ficam apenas no seu computador/Pi — servidos localmente ou por Tailscale Funnel com proteção.

> O `index.html` lista os 3 formulários — acessível pela raiz do domínio.

## Backup e restauração

Os scripts `backup.sh` e `restore.sh` ficam na raiz do projeto e operam sobre o container Docker — não precisam que a API esteja parada.

### Como funciona o backup

```bash
./backup.sh
```

Isso faz:
1. Gera uma cópia binária do SQLite (`.db`) dentro do container
2. Exporta todas as tabelas para `.json`
3. Compacta ambos em um **`.7z` criptografado** e remove os arquivos soltos
4. Envia o `.7z` para um host remoto via rsync (se configurado)
5. Mantém os **últimos 7** backups, apaga os mais antigos

O resultado em `backups/`:
```
backups/
├── forms_2026-06-21_030000.7z   ← backup de hoje
├── forms_2026-06-20_030000.7z   ← backup de ontem
└── forms_2026-06-19_030000.7z   ← ...
```

### Configurar senha do .7z

Edite a variável `ZIP_PASSWORD` no topo do `backup.sh` (e também no `restore.sh` com a **mesma** senha):

```bash
ZIP_PASSWORD="sua-senha-aqui"
```

### Configurar envio remoto

Edite as variáveis no topo do `backup.sh`:

```bash
REMOTE_HOST="usuario@ip-do-servidor"
REMOTE_DIR="/caminho/no/servidor"
SSH_KEY="$HOME/.ssh/id_ed25519"    # opcional
```

Envio é feito via rsync sobre SSH. Se `SSH_KEY` estiver vazio, usa a chave padrão.

### Agendar via cron (diário, às 3h)

```bash
crontab -e
```

Adicione:
```
0 3 * * * /home/pi/nlc-forms/backup.sh >> /home/pi/nlc-forms/backup.log 2>&1
```

### Restaurar

```bash
# Listar backups disponíveis
./restore.sh --list

# Restaurar de .db
./restore.sh backups/forms_2026-06-20_030000.db

# Restaurar de .7z (extrai automaticamente com a senha)
./restore.sh backups/forms_2026-06-21_030000.7z
```

O script salva automaticamente o estado atual antes de sobrescrever (`pre_restore_<timestamp>.db`), então é possível reverter se restaurar o backup errado.

## Acessar os dados diretamente

Os dados ficam no volume Docker `nlc-forms_forms_data`.

```bash
docker cp nlc-forms-api:/data/forms.db ./forms.db
```

Abrir com [DB Browser for SQLite](https://sqlitebrowser.org/) para consultar ou exportar CSV.

## Banco de dados

**Tabelas de triagem** (preenchidas pelo cliente): `triagem_suporte`, `triagem_seguranca`, `triagem_desenvolvimento` — campos específicos por serviço, todas com `codigo` (NLC-XXXX-XXXX) e `token` (link de acesso usado).

**`tokens`** — controla os links de acesso único: `token`, `servico`, `criado_em`, `expira_em`, `usado`, `usado_em`, `nota`.

**`catalogo_itens`** — itens de orçamento com preço sugerido por serviço (`servico`, `nome`, `valor`, `ativo`). Pré-populado com itens comuns na primeira execução — edite direto no banco se quiser ajustar preços.

**`execucao`** — o que você preenche no painel: `codigo` (vincula à triagem), `status`, `diagnostico`, `servicos_realizados`, `recomendacoes`, `observacoes_internas` (não aparece no PDF), `itens_json`, `valor_total`, `data_atendimento`, `validade_orcamento` (exibido no PDF como "Garantia válida até").

## Endpoints

| Método | Rota | Uso |
|---|---|---|
| POST | `/admin/gerar-token` | Gera link de triagem (requer `X-Admin-Key`) |
| GET | `/token/{token}/validar` | Frontend valida o token antes de mostrar o form |
| POST | `/triagem/suporte` | Cliente envia a triagem de suporte |
| POST | `/triagem/seguranca` | Cliente envia a triagem de segurança |
| POST | `/triagem/desenvolvimento` | Cliente envia a triagem de dev |
| GET | `/consulta?codigo=X` | Consulta pública por código |
| GET | `/consulta?email=X` | Consulta por e-mail (requer `X-Admin-Key`) |
| GET | `/admin/triagem/{codigo}` | Painel busca triagem + execução (requer admin) |
| GET | `/admin/triagens` | Lista todas as triagens com filtros e paginação (requer admin) |
| GET | `/admin/catalogo?servico=X` | Painel busca itens do catálogo (requer admin) |
| POST | `/admin/execucao` | Painel salva o atendimento (requer admin) |
| GET | `/admin/relatorio/{codigo}.pdf` | Gera e baixa o PDF final (requer admin) |
| POST | `/admin/enviar-pdf` | Envia o PDF por e-mail para o cliente (requer admin) |
| GET | `/health` | Verificação de status |
