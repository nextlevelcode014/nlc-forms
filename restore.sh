#!/bin/bash
#
# restore.sh — Restaura o banco de dados nlc-forms a partir de um backup .db
#
# ATENÇÃO: substitui completamente o banco atual. Os dados existentes
# antes da restauração são salvos em backups/pre_restore_<timestamp>.db
# por segurança, caso precise reverter.
#
# Uso:
#   ./restore.sh backups/forms_2026-06-20_030000.db
#
# Listar backups disponíveis:
#   ./restore.sh --list

set -euo pipefail

CONTAINER_NAME="nlc-forms-api"
BACKUP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/backups"

if [ "${1:-}" == "--list" ] || [ -z "${1:-}" ]; then
  echo "Backups disponíveis em ${BACKUP_DIR}:"
  echo ""
  ls -lht "${BACKUP_DIR}"/forms_*.db 2>/dev/null | awk '{print "  " $NF "  (" $5 ", " $6, $7, $8 ")"}' || echo "  Nenhum backup encontrado."
  echo ""
  echo "Uso: ./restore.sh <caminho-do-arquivo.db>"
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

echo "ATENÇÃO: isso vai substituir o banco de dados atual por:"
echo "  ${BACKUP_FILE}"
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

# ── 2. Copia o backup escolhido para dentro do container ────
docker cp "$BACKUP_FILE" "${CONTAINER_NAME}:/data/forms.db"

# ── 3. Reinicia o container para garantir que a API recarregue limpa ──
echo "Reiniciando o container..."
docker restart "$CONTAINER_NAME" >/dev/null

sleep 2
echo ""
echo "✓ Restauração concluída a partir de: ${BACKUP_FILE}"
echo "  Verifique com: curl http://localhost:8000/health"
