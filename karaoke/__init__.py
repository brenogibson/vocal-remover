"""Modulo de geracao de karaoke: transcricao, alinhamento, ASS e video."""

from pathlib import Path

from .align import align
from .ass import to_ass, write_ass
from .burn import burn
from .srt import to_srt, write_srt
from .transcribe import transcribe


def generate(
    vocals_path: str | Path,
    no_vocals_path: str | Path,
    output_path: str | Path,
    lyrics: str | None = None,
    whisper_model: str = "base",
    language: str | None = None,
) -> Path:
    """Pipeline completo: transcricao -> alinhamento -> ASS -> video MP4.

    Args:
        vocals_path:     faixa de voz extraida (vocals.mp3)
        no_vocals_path:  faixa instrumental (no_vocals.mp3)
        output_path:     caminho do video de saida (.mp4)
        lyrics:          letra original (opcional); sobrepoe o texto da transcricao
        whisper_model:   modelo Whisper ("tiny", "base", "small", "medium", "large")
        language:        idioma do audio (ex: "pt", "en"); None = deteccao automatica

    Retorna:
        Path do video MP4 gerado
    """
    vocals_path    = Path(vocals_path)
    no_vocals_path = Path(no_vocals_path)
    output_path    = Path(output_path)

    segments = transcribe(vocals_path, model=whisper_model, language=language)

    if lyrics and lyrics.strip():
        segments = align(segments, lyrics)

    ass_path = output_path.with_suffix(".ass")
    write_ass(segments, ass_path)

    return burn(no_vocals_path, ass_path, output_path)


__all__ = [
    "generate",
    "transcribe",
    "align",
    "to_ass", "write_ass",
    "to_srt", "write_srt",
    "burn",
]
