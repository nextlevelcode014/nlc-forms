# nlc-forms

Sistema de triagem, atendimento e relatório de clientes — NextLevelCode.

## Estrutura

```
nlc-forms/
├── backend/
│   ├── main.py              # FastAPI + SQLite — toda a API
│   ├── pdf_relatorio.py     # Geração do PDF final (reportlab)
│   ├── pyproject.toml
│   └── Dockerfile
├── frontend/
│   ├── triagem-suporte.html         # Formulário do cliente — Suporte Técnico
│   ├── triagem-seguranca.html       # Formulário do cliente — Segurança Digital
│   ├── triagem-desenvolvimento.html # Formulário do cliente — Dev & Automação
│   ├── admin-gerar-token.html       # Você gera o link a enviar no WhatsApp
│   └── painel-atendimento.html      # Você preenche o atendimento e gera o PDF
├── scripts/
│   ├── backup.sh             # Backup .db + .json, retenção de 7 dias
│   └── restore.sh            # Restaura a partir de um backup .db
└── docker-compose.yml
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

Rode um servidor estático dentro da pasta `frontend/`:

```bash
cd frontend
python3 -m http.server 9080
```

Acesse:
- `http://localhost:9080/admin-gerar-token.html` — gerar link de triagem
- `http://localhost:9080/painel-atendimento.html` — atender e gerar PDF

## Configuração (docker-compose.yml)

| Variável | Descrição |
|---|---|
| `ALLOWED_ORIGINS` | Domínios que podem chamar a API (CORS) |
| `ADMIN_KEY` | Chave usada para gerar tokens e acessar o painel — **troque o valor padrão** |
| `TOKEN_TTL_HOURS` | Validade padrão dos links de triagem, em horas |
| `SMTP_HOST` / `SMTP_PORT` / `SMTP_USER` / `SMTP_PASS` / `SMTP_FROM` | Configuração de e-mail. Deixe `SMTP_HOST` vazio para desativar notificações |
| `NOTIFY_TO` | Seu e-mail — recebe a notificação de nova triagem |
| `PAINEL_BASE_URL` | URL base de onde o frontend está servido — usada para montar o link no e-mail |

## Produção no Raspberry Pi

### 1. Copiar o projeto para o Pi

```bash
scp -r nlc-forms/ pi@<ip-do-pi>:~/
```

### 2. Atualizar configuração no docker-compose.yml

```yaml
ALLOWED_ORIGINS: "https://nextlevelcode.pro,https://www.nextlevelcode.pro"
ADMIN_KEY: "<gere uma chave forte aqui>"
PAINEL_BASE_URL: "https://<seu-dominio-do-painel>"
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

### 5. Atualizar API_BASE nos arquivos frontend

Em cada um dos 5 arquivos HTML, trocar:
```javascript
const API_BASE = "http://localhost:8000";
```
para:
```javascript
const API_BASE = "https://<nome-do-pi>.tail12345.ts.net";
```

Depois fazer deploy dos HTMLs de triagem na Vercel (públicos).

**Importante:** `admin-gerar-token.html` e `painel-atendimento.html` são de uso exclusivamente seu — não publique num caminho óbvio/indexado. A proteção real é a `ADMIN_KEY`, mas evite expor a URL desnecessariamente.

## Backup e restauração

Os scripts ficam em `scripts/` e operam sobre o container Docker — não precisam que a API esteja parada.

### Configurar o backup automático no Pi

```bash
# Tornar os scripts executáveis (necessário após copiar para o Pi)
chmod +x scripts/backup.sh scripts/restore.sh

# Testar manualmente primeiro
./scripts/backup.sh
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
0 3 * * * /home/pi/nlc-forms/scripts/backup.sh >> /home/pi/nlc-forms/scripts/backup.log 2>&1
```

Verifique se está rodando:

```bash
crontab -l
tail -f scripts/backup.log
```

### Restaurar um backup

```bash
# Listar backups disponíveis
./scripts/restore.sh --list

# Restaurar um específico
./scripts/restore.sh backups/forms_2026-06-20_030000.db
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
| GET | `/consulta?codigo=X` ou `?email=X` | Cliente consulta status pelo código ou e-mail |
| GET | `/admin/triagem/{codigo}` | Painel busca triagem + execução (requer admin) |
| GET | `/admin/catalogo?servico=X` | Painel busca itens do catálogo (requer admin) |
| POST | `/admin/execucao` | Painel salva o atendimento (requer admin) |
| GET | `/admin/relatorio/{codigo}.pdf` | Gera e baixa o PDF final (requer admin) |
| GET | `/health` | Verificação de status |
