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
│       ├── painel-atendimento.html
│       └── logo.png
├── compose.yml               # Docker Compose com env vars
├── .env.example              # Template de configuração (commitado)
├── .env                      # Configuração real (ignorado pelo git)
├── backup.sh                 # Backup .db + .json, retenção de 7 dias
└── restore.sh                # Restaura a partir de um backup .db
```

## Fluxo completo

```
1. Cliente conversa com você no WhatsApp
2. Você abre admin-gerar-token.html, gera um link de acesso único
3. Manda o link pro cliente
4. Cliente abre o link, preenche a triagem, recebe um código (NLC-XXXX-XXXX)
5. Você recebe um e-mail de notificação (se SMTP configurado)
6. Você abre painel-atendimento.html, busca pelo código
7. Preenche diagnóstico, serviços realizados, recomendações e itens de orçamento
8. Gera o PDF final — documento pronto para enviar ao cliente
```

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
python3 -m http.server 9080 -d frontend/admin &
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
| `PAINEL_BASE_URL` | `http://localhost:9080` | URL base do frontend |
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

### Configurar o backup automático no Pi

```bash
# Tornar os scripts executáveis
chmod +x backup.sh restore.sh

# Testar manualmente primeiro
./backup.sh
```

Isso cria a pasta `backups/` com dois arquivos por execução:
- `forms_YYYY-MM-DD_HHMMSS.db` — cópia binária completa, restauração rápida
- `forms_YYYY-MM-DD_HHMMSS.json` — exportação legível de todas as tabelas

Mantém automaticamente os **últimos 7** backups de cada tipo, apagando os mais antigos.

### Agendar via cron (diário, às 3h da manhã)

```bash
crontab -e
```

Adicione a linha (ajuste o caminho para onde o projeto está no Pi):

```
0 3 * * * /home/pi/nlc-forms/backup.sh >> /home/pi/nlc-forms/backup.log 2>&1
```

Verifique se está rodando:

```bash
crontab -l
tail -f backup.log
```

### Restaurar um backup

```bash
# Listar backups disponíveis
./restore.sh --list

# Restaurar um específico
./restore.sh backups/forms_2026-06-20_030000.db
```

O script salva automaticamente o estado atual antes de sobrescrever (`pre_restore_<timestamp>.db`), então é possível reverter se restaurar o backup errado.

### Levar os backups para fora do Pi

Os backups ficam no SD card junto com o resto do projeto — se o cartão falhar, eles também se perdem. Vale copiar periodicamente para outro lugar:

```bash
# Exemplo: copiar para outro computador na rede via rsync
rsync -avz pi@<ip-do-pi>:~/nlc-forms/backups/ ./backups-nlc/
```

Ou sincronizar a pasta `backups/` com um serviço próprio (Nextcloud, por exemplo), já que você já mantém esse ambiente.

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

**`execucao`** — o que você preenche no painel: `codigo` (vincula à triagem), `status`, `diagnostico`, `servicos_realizados`, `recomendacoes`, `observacoes_internas` (não aparece no PDF), `itens_json`, `valor_total`, `data_atendimento`.

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
| GET | `/admin/catalogo?servico=X` | Painel busca itens do catálogo (requer admin) |
| POST | `/admin/execucao` | Painel salva o atendimento (requer admin) |
| GET | `/admin/relatorio/{codigo}.pdf` | Gera e baixa o PDF final (requer admin) |
| GET | `/health` | Verificação de status |
