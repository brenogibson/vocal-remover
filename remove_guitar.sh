#!/usr/bin/env bash
set -euo pipefail

if [ $# -lt 1 ]; then
    echo "Uso: $0 <arquivo_audio> [diretorio_saida]"
    echo "Exemplo: $0 musica.mp3 ./output"
    exit 1
fi

INPUT="$1"
OUTPUT_DIR="${2:-./separated}"

if [ ! -f "$INPUT" ]; then
    echo "Erro: arquivo '$INPUT' nao encontrado."
    exit 1
fi

mkdir -p "$OUTPUT_DIR"

# htdemucs_6s = modelo de 6 stems (drums, bass, other, vocals, guitar, piano)
# --two-stems=guitar: separa apenas em guitar + no_guitar (tudo menos guitarra)
# --mp3: salva em mp3
# --mp3-bitrate 320: bitrate maximo
# --clip-mode clamp: evita clipping no audio

echo "Removendo guitarra de: $INPUT"
echo "Modelo: htdemucs_6s (6 stems: drums, bass, other, vocals, guitar, piano)"
echo "Isso pode levar alguns minutos..."

python3.13 -m demucs \
    --name htdemucs_6s \
    --two-stems guitar \
    --mp3 \
    --mp3-bitrate 320 \
    --clip-mode clamp \
    --out "$OUTPUT_DIR" \
    "$INPUT"

BASENAME="$(basename "${INPUT%.*}")"
RESULT_DIR="$OUTPUT_DIR/htdemucs_6s/$BASENAME"

echo ""
echo "Concluido! Arquivos gerados em: $RESULT_DIR/"
echo "  - no_guitar.mp3  (tudo menos guitarra)"
echo "  - guitar.mp3     (apenas guitarra isolada)"
