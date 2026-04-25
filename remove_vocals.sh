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

# htdemucs_ft = modelo fine-tuned, melhor qualidade para separacao de vocais
# --two-stems=vocals: separa apenas em vocals + no_vocals (instrumental)
# --mp3: salva em mp3 (remover para WAV lossless)
# --mp3-bitrate 320: bitrate maximo
# --clip-mode clamp: evita clipping no audio

echo "Removendo vocais de: $INPUT"
echo "Modelo: htdemucs_ft (fine-tuned, melhor qualidade)"
echo "Isso pode levar alguns minutos..."

python3.13 -m demucs \
    --name htdemucs_ft \
    --two-stems vocals \
    --mp3 \
    --mp3-bitrate 320 \
    --clip-mode clamp \
    --out "$OUTPUT_DIR" \
    "$INPUT"

BASENAME="$(basename "${INPUT%.*}")"
RESULT_DIR="$OUTPUT_DIR/htdemucs_ft/$BASENAME"

echo ""
echo "Concluido! Arquivos gerados em: $RESULT_DIR/"
echo "  - no_vocals.mp3  (instrumental, sem vocais)"
echo "  - vocals.mp3     (apenas vocais)"
