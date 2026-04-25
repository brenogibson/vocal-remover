"""Transcreve audio de voz para segmentos com timestamps via Whisper."""

from pathlib import Path

AUDIO_EXTS = {".mp3", ".wav", ".flac", ".ogg", ".m4a", ".opus"}

# Marcadores de ruido que o Whisper insere — descartados
_NOISE_MARKERS = {"[music]", "[applause]", "[laughter]", "[noise]", "[silence]", "(music)"}


def transcribe(
    audio_path: str | Path,
    model: str = "base",
    language: str | None = None,
    device: str | None = None,
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

    result = wmodel.transcribe(
        str(audio_path),
        language=language,
        fp16=(device == "cuda"),
        verbose=False,
    )

    segments = []
    for seg in result.get("segments", []):
        text = seg.get("text", "").strip()
        if not text:
            continue
        if text.lower() in _NOISE_MARKERS:
            continue
        segments.append({
            "text":  text,
            "start": float(seg["start"]),
            "end":   float(seg["end"]),
        })

    return segments
