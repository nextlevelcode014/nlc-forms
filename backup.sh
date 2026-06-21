#!/bin/bash
#
# backup.sh — Backup do banco de dados nlc-forms
#
# Gera dois arquivos por execução:
#   - forms_YYYY-MM-DD_HHMMSS.db    (cópia binária completa do SQLite)
#   - forms_YYYY-MM-DD_HHMMSS.json  (exportação legível de todas as tabelas)
#
# Compacta ambos em um .7z criptografado e envia para host remoto.
#
# Mantém os últimos 7 backups locais de cada tipo, apaga os mais antigos.
#
# Uso manual:
#   ./backup.sh
#
# Uso via cron (diário às 3h da manhã):
#   0 3 * * * /home/pi/nlc-forms/scripts/backup.sh >> /home/pi/nlc-forms/scripts/backup.log 2>&1

set -euo pipefail

# ── Configuração ─────────────────────────────────────────────
CONTAINER_NAME="nlc-forms-api"
BACKUP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/backups"
RETENCAO=7
ZIP_PASSWORD="SUA_SENHA_AQUI"

# ── Destino remoto via rsync/SSH (opcional) ──────────────────
REMOTE_HOST="marta@100.123.47.58"
REMOTE_DIR="/home/marta/Work/.backups/forms"
SSH_KEY=""
SSH_PORT="22"
# ─────────────────────────────────────────────────────────────

TIMESTAMP=$(date +"%Y-%m-%d_%H%M%S")
DB_BACKUP="${BACKUP_DIR}/forms_${TIMESTAMP}.db"
JSON_BACKUP="${BACKUP_DIR}/forms_${TIMESTAMP}.json"
SEVENZ_BACKUP="${BACKUP_DIR}/forms_${TIMESTAMP}.7z"

mkdir -p "$BACKUP_DIR"

echo "[$(date +'%Y-%m-%d %H:%M:%S')] Iniciando backup..."

# ── 1. Verifica se o container está rodando ────────────────
if ! docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
  echo "ERRO: container '${CONTAINER_NAME}' não está rodando. Backup abortado."
  exit 1
fi

# ── 2. Backup binário (.db) ─────────────────────────────────
docker exec "$CONTAINER_NAME" python3 -c "
import sqlite3
src = sqlite3.connect('/data/forms.db')
dst = sqlite3.connect('/tmp/backup_temp.db')
src.backup(dst)
src.close()
dst.close()
"
docker cp "${CONTAINER_NAME}:/tmp/backup_temp.db" "$DB_BACKUP"
docker exec "$CONTAINER_NAME" rm -f /tmp/backup_temp.db

echo "  ✓ Backup .db salvo em: $DB_BACKUP"

# ── 3. Exportação JSON (todas as tabelas) ───────────────────
docker exec "$CONTAINER_NAME" python3 -c "
import sqlite3
import json

conn = sqlite3.connect('/data/forms.db')
conn.row_factory = sqlite3.Row

tabelas = [
    'tokens', 'triagem_suporte', 'triagem_seguranca',
    'triagem_desenvolvimento', 'catalogo_itens', 'execucao',
]

dump = {}
for tabela in tabelas:
    try:
        rows = conn.execute(f'SELECT * FROM {tabela}').fetchall()
        dump[tabela] = [dict(r) for r in rows]
    except sqlite3.OperationalError:
        dump[tabela] = []

print(json.dumps(dump, ensure_ascii=False, indent=2))
" >"$JSON_BACKUP"

echo "  ✓ Backup .json salvo em: $JSON_BACKUP"

# ── 4. Compactação criptografada em .7z ─────────────────────
echo "Compactando e criptografando..."
7z a -p"${ZIP_PASSWORD}" -mhe=on "${SEVENZ_BACKUP}" "${DB_BACKUP}" "${JSON_BACKUP}" >/dev/null

rm -f "$DB_BACKUP" "$JSON_BACKUP"

echo "  ✓ .7z criptografado salvo em: $SEVENZ_BACKUP"

# ── 5. Envio remoto via rsync/SSH (se configurado) ──────────
if [ -n "$REMOTE_HOST" ] && [ -n "$REMOTE_DIR" ]; then
  echo "Enviando backups para ${REMOTE_HOST}:${REMOTE_DIR} ..."

  RSYNC_SSH_OPTS="ssh -p ${SSH_PORT}"
  if [ -n "$SSH_KEY" ]; then
    RSYNC_SSH_OPTS="${RSYNC_SSH_OPTS} -i ${SSH_KEY}"
  fi

  if rsync -az --partial -e "${RSYNC_SSH_OPTS}" \
    "${SEVENZ_BACKUP}" \
    "${REMOTE_HOST}:${REMOTE_DIR}/"; then
    echo "  ✓ .7z enviado com sucesso para o host remoto."
  else
    echo "  ✗ AVISO: falha ao enviar backups via rsync. O backup local foi mantido normalmente."
  fi
else
  echo "  (envio remoto desativado)"
fi

# ── 6. Limpeza — mantém apenas os últimos N backups locais ──
cd "$BACKUP_DIR"

SEVENZ_COUNT=$(ls -1 forms_*.7z 2>/dev/null | wc -l)
if [ "$SEVENZ_COUNT" -gt "$RETENCAO" ]; then
  ls -1t forms_*.7z | tail -n +$((RETENCAO + 1)) | xargs rm -f
  echo "  ✓ Backups .7z antigos removidos (mantendo os últimos ${RETENCAO})"
fi

TAMANHO_TOTAL=$(du -sh "$BACKUP_DIR" | cut -f1)
echo "[$(date +'%Y-%m-%d %H:%M:%S')] Backup concluído. Tamanho total da pasta: ${TAMANHO_TOTAL}"
echo "---"
