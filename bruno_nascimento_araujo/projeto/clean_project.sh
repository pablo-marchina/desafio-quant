#!/usr/bin/env bash
# clean_project.sh — remove arquivos/pastas gerados que nao devem ser versionados.
#
# Uso:
#   ./clean_project.sh
#
# O script so remove itens conhecidos de cache/log/estado/build (ver secao
# "REMOVER" abaixo). Binarios e dados reais do Qdrant (qdrant, storage/,
# snapshots/, .qdrant-initialized) NAO sao apagados do disco — apenas
# ignorados pelo git (.gitignore) — pois representam trabalho local caro de
# refazer (embeddings vetorizados, download do binario do Qdrant).
set -euo pipefail
cd "$(dirname "$0")"

echo "=========================================="
echo " NVIDIA Startup AI Radar — Limpeza do Projeto"
echo "=========================================="

remove_path() {
    local path="$1"
    if [ -e "$path" ] || [ -L "$path" ]; then
        echo "  x Removendo: $path"
        rm -rf -- "$path"
    fi
}

remove_matches() {
    # $1 = descricao (log), demais args = argumentos de 'find' apos '.'
    local desc="$1"; shift
    while IFS= read -r -d '' f; do
        remove_path "$f"
    done < <(find . -not -path "./.git/*" "$@" -print0 2>/dev/null)
}

echo ""
echo "--- Ambiente virtual (removido primeiro para nao ser varrido pelo find) ---"
remove_path ".venv"
remove_path "venv"
remove_path "env"

echo ""
echo "--- Logs ---"
remove_path "classificacao.log"
remove_path "nohup.out"
remove_matches "logs" -maxdepth 1 -type f -name "*.log"

echo ""
echo "--- Estado / cache de execucao ---"
remove_path "nvidia_ingest_state.json"

echo ""
echo "--- Cache e compilados Python ---"
remove_matches "__pycache__" -type d -name "__pycache__"
remove_matches "*.pyc" -type f -name "*.pyc"
remove_matches "*.pyo" -type f -name "*.pyo"
remove_path ".pytest_cache"
remove_path ".mypy_cache"

echo ""
echo "--- Empacotamento Python ---"
remove_matches "*.egg-info" -maxdepth 1 -type d -name "*.egg-info"
remove_path "dist"
remove_path "build"

echo ""
echo "--- Relatorios gerados (pasta reports/ e mantida com .gitkeep) ---"
if [ -d "reports" ]; then
    find reports -maxdepth 1 -type f ! -name ".gitkeep" -print0 2>/dev/null |
        while IFS= read -r -d '' f; do remove_path "$f"; done
    touch reports/.gitkeep
    echo "  + reports/.gitkeep criado/mantido"
fi

echo ""
echo "--- Arquivos temporarios de sistema ---"
remove_matches ".DS_Store" -type f -name ".DS_Store"
remove_matches "Thumbs.db" -type f -name "Thumbs.db"
remove_matches "*.tmp" -type f -name "*.tmp"

echo ""
echo "=========================================="
echo " Itens encontrados mas NAO removidos (dados/binarios reais do Qdrant):"
echo "=========================================="
for item in qdrant storage snapshots .qdrant-initialized; do
    if [ -e "$item" ]; then
        echo "  - $item  (mantido no disco; ja coberto pelo .gitignore)"
    fi
done

echo ""
echo "=========================================="
echo " Conteudo atual da raiz do projeto:"
echo "=========================================="
ls -la .

echo ""
echo "Limpeza concluida. Rode 'git status' para conferir o que sera commitado."
