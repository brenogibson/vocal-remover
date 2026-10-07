#!/usr/bin/env bash
set -euo pipefail

if [ $# -lt 2 ]; then
    echo "Uso: $0 <arquivo_audio> <semitons> [arquivo_saida]"
    echo "Exemplo: $0 musica.mp3 2 musica_up.mp3"
    echo "         (use valores negativos como -3 para abaixar o tom)"
    exit 1
fi

INPUT="$1"
SEMITONES="$2"
OUTPUT="${3:-${INPUT%.*}_pitch${SEMITONES}.mp3}"

if [ ! -f "$INPUT" ]; then
    echo "Erro: arquivo '$INPUT' nao encontrado."
    exit 1
fi

echo "Mudando o tom de: $INPUT"
echo "Transpondo $SEMITONES semitons..."

"$(dirname "$0")/.venv/bin/python3" -m pitch.change_pitch "$INPUT" "$SEMITONES" "$OUTPUT"

echo ""
echo "Concluido! Arquivo gerado em: $OUTPUT"
