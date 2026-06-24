#!/bin/bash
#
# setup-producao.sh — Substitui placeholders para o ambiente de produção
#
# Uso:
#   ./setup-producao.sh https://meudominio.com:8000
#
# Isso troca __API_BASE__ pela URL real em todos os HTMLs do frontend.

set -euo pipefail

if [ $# -ne 1 ]; then
  echo "Uso: $0 <URL_DA_API>"
  echo "Ex:  $0 https://api.meudominio.com"
  exit 1
fi

API_BASE="${1%/}"

echo "Substituindo __API_BASE__ por ${API_BASE} ..."

find frontend -name '*.html' -exec sed -i "s|__API_BASE__|${API_BASE}|g" {} +

echo "✓ Concluído. Arquivos modificados:"
grep -rl "$API_BASE" frontend/ --include='*.html' | sed 's/^/  /'
