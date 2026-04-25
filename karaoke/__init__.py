"""Modulo de geracao de karaoke: transcricao, alinhamento, SRT e video."""

from pathlib import Path

from .align import align
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
    """Pipeline completo: transcricao -> alinhamento -> SRT -> video MP4.

    Args:
        vocals_path:     faixa de voz extraida (vocals.mp3)
        no_vocals_path:  faixa instrumental (no_vocals.mp3)
        output_path:     caminho do video de saida (.mp4)
        lyrics:          letra original (opcional); se fornecida, sobrepoe a transcricao
        whisper_model:   modelo Whisper a usar ("tiny", "base", "small", "medium", "large")
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

    srt_path = output_path.with_suffix(".srt")
    write_srt(segments, srt_path)

    return burn(no_vocals_path, srt_path, output_path)


__all__ = ["generate", "transcribe", "align", "to_srt", "write_srt", "burn"]
