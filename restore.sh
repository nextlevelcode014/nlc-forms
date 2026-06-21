#!/bin/bash
#
# restore.sh — Restaura o banco de dados nlc-forms a partir de um backup
#
# Aceita arquivos .db ou .7z (criptografados com a mesma senha do backup.sh).
# ATENÇÃO: substitui completamente o banco atual. Os dados existentes
# antes da restauração são salvos em backups/pre_restore_<timestamp>.db
# por segurança, caso precise reverter.
#
# Uso:
#   ./restore.sh backups/forms_2026-06-20_030000.db
#   ./restore.sh backups/forms_2026-06-20_030000.7z
#
# Listar backups disponíveis:
#   ./restore.sh --list

set -euo pipefail

CONTAINER_NAME="nlc-forms-api"
BACKUP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/backups"
ZIP_PASSWORD="SUA_SENHA_AQUI"

if [ "${1:-}" == "--list" ] || [ -z "${1:-}" ]; then
  echo "Backups disponíveis em ${BACKUP_DIR}:"
  echo ""
  ls -lht "${BACKUP_DIR}"/forms_*.7z 2>/dev/null | awk '{print "  " $NF "  (" $5 ", " $6, $7, $8 ")"}'
  ls -lht "${BACKUP_DIR}"/forms_*.db 2>/dev/null | awk '{print "  " $NF "  (" $5 ", " $6, $7, $8 ")"}'
  if ! ls "${BACKUP_DIR}"/forms_*.{7z,db} 2>/dev/null | grep -q .; then
    echo "  Nenhum backup encontrado."
  fi
  echo ""
  echo "Uso: ./restore.sh <caminho-do-arquivo.db> ou ./restore.sh <caminho-do-arquivo.7z>"
  exit 0
fi

BACKUP_FILE="$1"

if [ ! -f "$BACKUP_FILE" ]; then
  echo "ERRO: arquivo '${BACKUP_FILE}' não encontrado."
  exit 1
fi

if ! docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
  echo "ERRO: container '${CONTAINER_NAME}' não está rodando."
  exit 1
fi

# ── Se for .7z, extrai o .db temporariamente ────────────────
if [[ "$BACKUP_FILE" == *.7z ]]; then
  echo "Arquivo .7z detectado. Extraindo..."
  TMP_DIR=$(mktemp -d)
  trap "rm -rf '$TMP_DIR'" EXIT

  7z x -p"${ZIP_PASSWORD}" "$BACKUP_FILE" -o"$TMP_DIR" >/dev/null

  DB_FILE=$(find "$TMP_DIR" -name "*.db" | head -1)
  if [ -z "$DB_FILE" ]; then
    echo "ERRO: nenhum arquivo .db encontrado dentro do .7z."
    exit 1
  fi
  echo "  ✓ Extraído: $(basename "$DB_FILE")"

  # Registra o nome original para exibir no final
  ORIGINAL_NAME=$(basename "$BACKUP_FILE")
  # Usa o caminho do .db extraído como BACKUP_FILE daqui pra frente
  RESTORE_SOURCE="$DB_FILE"
else
  RESTORE_SOURCE="$BACKUP_FILE"
  ORIGINAL_NAME=$(basename "$BACKUP_FILE")
fi

echo "ATENÇÃO: isso vai substituir o banco de dados atual por:"
echo "  ${ORIGINAL_NAME}"
echo ""
read -p "Confirma a restauração? (digite 'sim' para continuar): " CONFIRMACAO

if [ "$CONFIRMACAO" != "sim" ]; then
  echo "Restauração cancelada."
  exit 0
fi

# ── 1. Backup de segurança do estado atual antes de sobrescrever ──
TIMESTAMP=$(date +"%Y-%m-%d_%H%M%S")
PRE_RESTORE_BACKUP="${BACKUP_DIR}/pre_restore_${TIMESTAMP}.db"

mkdir -p "$BACKUP_DIR"
docker cp "${CONTAINER_NAME}:/data/forms.db" "$PRE_RESTORE_BACKUP" 2>/dev/null &&
  echo "✓ Estado atual salvo em: $PRE_RESTORE_BACKUP" ||
  echo "(aviso: não havia banco atual para preservar — seguindo normalmente)"

# ── 2. Copia o backup para dentro do container ────
docker cp "$RESTORE_SOURCE" "${CONTAINER_NAME}:/data/forms.db"

# ── 3. Reinicia o container ──
echo "Reiniciando o container..."
docker restart "$CONTAINER_NAME" >/dev/null

sleep 2
echo ""
echo "✓ Restauração concluída a partir de: ${ORIGINAL_NAME}"
echo "  Verifique com: curl http://localhost:8000/health"
