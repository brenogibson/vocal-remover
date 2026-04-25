#!/usr/bin/env bash
set -euo pipefail

if [ $# -lt 1 ]; then
    echo "Uso: $0 <url> [diretorio_saida]"
    echo "Exemplo: $0 https://www.youtube.com/watch?v=abc123"
    exit 1
fi

URL="$1"
OUTPUT_DIR="${2:-.}"

mkdir -p "$OUTPUT_DIR"

# Detecta navegador disponivel para cookies
BROWSER=""
for b in firefox chromium chrome brave; do
    if command -v "$b" &>/dev/null || [ -d "$HOME/.mozilla" ] && [ "$b" = "firefox" ]; then
        BROWSER="$b"
        break
    fi
done

COOKIE_ARGS=()
if [ -n "$BROWSER" ]; then
    echo "Usando cookies do navegador: $BROWSER"
    COOKIE_ARGS=(--cookies-from-browser "$BROWSER")
fi

echo "Baixando MP3 de: $URL"
yt-dlp \
    "${COOKIE_ARGS[@]}" \
    --remote-components ejs:github \
    --extract-audio \
    --audio-format mp3 \
    --audio-quality 0 \
    --output "$OUTPUT_DIR/%(title)s.%(ext)s" \
    "$URL"

echo "Download concluido! Arquivo salvo em: $OUTPUT_DIR/"
