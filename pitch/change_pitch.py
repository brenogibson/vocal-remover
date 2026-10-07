"""Muda o tom de um audio transpondo por N semitons via ffmpeg.

Estrategia (sem bibliotecas externas de pitch como rubberband/librosa):
  1. Descobre a taxa de amostragem (sample rate) do audio com ffprobe
  2. Calcula a razao de frequencia: ratio = 2 ** (semitons / 12)
  3. Reescreve a taxa de amostragem com asetrate (muda tom + duracao)
  4. Volta a taxa original com aresample (sem alterar o tom ja deslocado)
  5. Corrige a duracao de volta ao original com atempo (1 / ratio)

Semitons positivos sobem o tom, negativos descem. A duracao do audio
e preservada porque o atempo compensa a mudanca de velocidade.
"""

import shutil
import subprocess
import sys
from pathlib import Path

# Faixa razoavel de transposicao, em semitons.
MIN_SEMITONES = -24
MAX_SEMITONES = 24

# Taxa de amostragem usada quando o ffprobe nao consegue descobrir a do audio.
DEFAULT_SAMPLE_RATE = 44100


def change_pitch(
    audio_path: str | Path,
    output_path: str | Path,
    semitones: float,
    overwrite: bool = True,
) -> Path:
    """Transpoe o audio por 'semitones' semitons preservando a duracao.

    Args:
        audio_path:  caminho do audio de entrada (.mp3, .wav, ...)
        output_path: caminho do audio de saida (.mp3 ou .wav)
        semitones:   quantidade de semitons (positivo sobe, negativo desce)
        overwrite:   sobrescrever a saida se ja existir

    Retorna:
        Path do audio gerado
    """
    if not shutil.which("ffmpeg"):
        raise RuntimeError("ffmpeg nao encontrado no PATH. Instale: sudo apt install ffmpeg")

    try:
        semitones = float(semitones)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Numero de semitons invalido: {semitones!r}") from exc

    if not (MIN_SEMITONES <= semitones <= MAX_SEMITONES):
        raise ValueError(
            f"Semitons fora da faixa permitida ({MIN_SEMITONES}..{MAX_SEMITONES}): {semitones}"
        )

    audio_path  = Path(audio_path)
    output_path = Path(output_path)

    if not audio_path.is_file():
        raise FileNotFoundError(f"Audio nao encontrado: {audio_path}")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Razao de frequencia correspondente aos semitons (cada oitava = 12 semitons).
    ratio = 2 ** (semitones / 12.0)

    sr = _get_sample_rate(audio_path)

    # asetrate: reinterpreta a taxa de amostragem -> desloca o tom (e a velocidade)
    # aresample: volta a taxa original mantendo o tom ja deslocado
    # atempo: corrige a velocidade/duracao de volta ao original (1/ratio)
    af = f"asetrate={sr}*{ratio},aresample={sr},atempo={1 / ratio}"

    # Escolhe o codec conforme a extensao da saida.
    ext = output_path.suffix.lower()
    if ext == ".wav":
        codec_args = ["-c:a", "pcm_s16le"]
    else:
        codec_args = ["-c:a", "libmp3lame", "-b:a", "320k"]

    cmd = [
        "ffmpeg",
        *(["-y"] if overwrite else []),
        "-i", str(audio_path),
        "-af", af,
        *codec_args,
        str(output_path),
    ]

    proc = subprocess.run(cmd, capture_output=True, text=True)

    if proc.returncode != 0:
        raise RuntimeError(
            f"ffmpeg falhou (code {proc.returncode}):\n{proc.stderr[-2000:]}"
        )

    return output_path


def _get_sample_rate(audio_path: Path) -> int:
    """Descobre a taxa de amostragem do audio via ffprobe (fallback 44100)."""
    cmd = [
        "ffprobe", "-v", "error",
        "-select_streams", "a:0",
        "-show_entries", "stream=sample_rate",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(audio_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    try:
        return int(result.stdout.strip())
    except (ValueError, TypeError):
        return DEFAULT_SAMPLE_RATE


# ── CLI ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Uso: python3 -m pitch.change_pitch <arquivo_audio> <semitons> <arquivo_saida>")
        print("Exemplo: python3 -m pitch.change_pitch musica.mp3 2 musica_up.mp3")
        print("         (use valores negativos como -3 para abaixar o tom)")
        sys.exit(1)

    in_path  = sys.argv[1]
    out_path = sys.argv[3]
    try:
        n_semitones = float(sys.argv[2])
    except ValueError:
        print(f"Erro: numero de semitons invalido: {sys.argv[2]}")
        sys.exit(1)

    try:
        result_path = change_pitch(in_path, out_path, n_semitones)
    except Exception as exc:
        print(f"Erro: {exc}")
        sys.exit(1)

    print(f"Concluido! Arquivo gerado em: {result_path}")
