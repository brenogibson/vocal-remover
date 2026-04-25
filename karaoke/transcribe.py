"""Transcreve audio de voz para segmentos com timestamps via Whisper.

Estrategia:
  1. Detecta periodos de silencio no audio (ffmpeg silencedetect)
  2. Divide o audio em chunks nos limites de silencio
  3. Transcreve cada chunk separadamente com Whisper
  4. Soma o offset absoluto de cada chunk aos timestamps relativos

Isso da timestamps muito mais precisos do que processar o arquivo inteiro,
porque o Whisper recebe frases curtas e isoladas.
"""

import re
import subprocess
import tempfile
from pathlib import Path

AUDIO_EXTS = {".mp3", ".wav", ".flac", ".ogg", ".m4a", ".opus"}
_NOISE_MARKERS = {"[music]", "[applause]", "[laughter]", "[noise]", "[silence]", "(music)"}


def transcribe(
    audio_path: str | Path,
    model: str = "base",
    language: str | None = None,
    device: str | None = None,
    silence_db: float = -35,
    silence_min_duration: float = 0.3,
    min_chunk_duration: float = 1.5,
) -> list[dict]:
    """Transcreve audio e retorna lista de segmentos com timestamps.

    Retorna:
        [{"text": str, "start": float, "end": float}, ...]
    """
    audio_path = Path(audio_path)

    if not audio_path.is_file():
        raise FileNotFoundError(f"Audio nao encontrado: {audio_path}")
    if audio_path.suffix.lower() not in AUDIO_EXTS:
        raise ValueError(f"Formato nao suportado: {audio_path.suffix}")

    try:
        import whisper
    except ImportError as e:
        raise ImportError(
            "openai-whisper nao instalado. Rode: pip install openai-whisper"
        ) from e

    if device is None:
        try:
            import torch
            device = "cuda" if torch.cuda.is_available() else "cpu"
        except ImportError:
            device = "cpu"

    wmodel = whisper.load_model(model, device=device)

    duration = _get_duration(audio_path)

    # Aplica noise gate para suprimir artifacts do Demucs antes de detectar silencio
    with tempfile.TemporaryDirectory() as pre_dir:
        gated_path = Path(pre_dir) / "gated.wav"
        _apply_gate(audio_path, gated_path)
        silences = _detect_silence(gated_path, silence_db, silence_min_duration)

    chunks = _speech_chunks(silences, duration, min_chunk_duration)

    # Sem silencias detectados: processa o arquivo inteiro
    if len(chunks) < 2:
        return _transcribe_file(wmodel, audio_path, offset=0.0,
                                language=language, device=device)

    all_segments: list[dict] = []
    with tempfile.TemporaryDirectory() as tmpdir:
        for i, (start, end) in enumerate(chunks):
            chunk_path = Path(tmpdir) / f"chunk_{i:04d}.wav"
            _extract_chunk(audio_path, start, end, chunk_path)
            segs = _transcribe_file(wmodel, chunk_path, offset=start,
                                    language=language, device=device)
            all_segments.extend(segs)

    return all_segments


# ── ffmpeg helpers ────────────────────────────────────────────────────────────

def _get_duration(audio_path: Path) -> float:
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(audio_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    try:
        return float(result.stdout.strip())
    except ValueError:
        return 600.0  # fallback: 10 minutos


def _detect_silence(
    audio_path: Path,
    noise_db: float,
    min_duration: float,
) -> list[tuple[float, float]]:
    cmd = [
        "ffmpeg", "-i", str(audio_path),
        "-af", f"silencedetect=noise={noise_db}dB:d={min_duration}",
        "-f", "null", "-",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)

    silences: list[tuple[float, float]] = []
    start: float | None = None
    for line in proc.stderr.splitlines():
        if "silence_start" in line:
            try:
                start = float(line.split("silence_start:")[1].strip())
            except (ValueError, IndexError):
                pass
        elif "silence_end" in line and start is not None:
            try:
                end_str = line.split("silence_end:")[1].split("|")[0].strip()
                silences.append((start, float(end_str)))
            except (ValueError, IndexError):
                pass
            start = None

    return silences


def _speech_chunks(
    silences: list[tuple[float, float]],
    total_duration: float,
    min_chunk: float,
) -> list[tuple[float, float]]:
    """Converte periodos de silencio em chunks de fala."""
    chunks: list[tuple[float, float]] = []
    prev_end = 0.0

    for sil_start, sil_end in silences:
        if sil_start > prev_end + 0.1:
            chunks.append((prev_end, sil_start))
        prev_end = sil_end

    if prev_end < total_duration - 0.1:
        chunks.append((prev_end, total_duration))

    # Mescla chunks curtos com o anterior (estende o fim do anterior)
    merged: list[tuple[float, float]] = []
    for chunk in chunks:
        dur = chunk[1] - chunk[0]
        if dur < min_chunk and merged:
            merged[-1] = (merged[-1][0], chunk[1])
        else:
            merged.append(chunk)

    # Descarta residuos muito curtos que sobraram
    return [c for c in merged if c[1] - c[0] >= 0.5]


def _apply_gate(audio_path: Path, out_path: Path):
    """Aplica noise gate para remover artifacts do Demucs entre frases."""
    cmd = [
        "ffmpeg", "-y", "-i", str(audio_path),
        "-af", "agate=threshold=0.03:attack=10:release=100",
        "-ac", "1", "-ar", "16000",
        str(out_path),
    ]
    subprocess.run(cmd, capture_output=True, check=True)


def _extract_chunk(audio_path: Path, start: float, end: float, out_path: Path):
    """Extrai trecho de audio como WAV mono 16kHz (formato ideal para Whisper)."""
    cmd = [
        "ffmpeg", "-y",
        "-i", str(audio_path),
        "-ss", str(start), "-to", str(end),
        "-ac", "1", "-ar", "16000",
        str(out_path),
    ]
    subprocess.run(cmd, capture_output=True, check=True)


# ── transcricao ───────────────────────────────────────────────────────────────

def _transcribe_file(
    wmodel,
    audio_path: Path,
    offset: float,
    language: str | None,
    device: str,
) -> list[dict]:
    result = wmodel.transcribe(
        str(audio_path),
        language=language,
        fp16=(device == "cuda"),
        verbose=False,
    )
    segments = []
    for seg in result.get("segments", []):
        text = seg.get("text", "").strip()
        if not text or text.lower() in _NOISE_MARKERS:
            continue
        segments.append({
            "text":  text,
            "start": float(seg["start"]) + offset,
            "end":   float(seg["end"])   + offset,
        })
    return segments
