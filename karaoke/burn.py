"""Gera video karaoke: fundo preto + audio + legenda queimada via ffmpeg."""

import shutil
import subprocess
from pathlib import Path


def burn(
    audio_path: str | Path,
    srt_path: str | Path,
    output_path: str | Path,
    resolution: tuple[int, int] = (1280, 720),
    fps: int = 30,
    overwrite: bool = True,
) -> Path:
    """Combina audio e legenda em video MP4 com fundo preto.

    Args:
        audio_path:  caminho para o audio (no_vocals.mp3)
        srt_path:    caminho para o arquivo .srt
        output_path: caminho do video de saida (.mp4)
        resolution:  (largura, altura) em pixels
        fps:         frames por segundo do video
        overwrite:   sobrescrever se ja existir

    Retorna:
        Path do video gerado
    """
    if not shutil.which("ffmpeg"):
        raise RuntimeError("ffmpeg nao encontrado no PATH. Instale: sudo apt install ffmpeg")

    audio_path  = Path(audio_path)
    srt_path    = Path(srt_path)
    output_path = Path(output_path)

    if not audio_path.is_file():
        raise FileNotFoundError(f"Audio nao encontrado: {audio_path}")
    if not srt_path.is_file():
        raise FileNotFoundError(f"SRT nao encontrado: {srt_path}")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    w, h = resolution
    font_size = max(18, h // 25)

    # O filtro subtitles precisa do path absoluto e sem caracteres problematicos
    srt_abs = str(srt_path.resolve()).replace("\\", "/").replace(":", "\\:")

    style = (
        f"FontSize={font_size},"
        "FontName=Arial,"
        "PrimaryColour=&H00FFFFFF,"   # branco
        "OutlineColour=&H00000000,"   # outline preto
        "Outline=2,"
        "Shadow=1,"
        "Alignment=2,"                # centro inferior
        "MarginV=40"
    )

    cmd = [
        "ffmpeg",
        *([ "-y"] if overwrite else []),
        "-f", "lavfi",
        "-i", f"color=c=black:s={w}x{h}:r={fps}",
        "-i", str(audio_path),
        "-filter_complex", f"[0:v]subtitles='{srt_abs}':force_style='{style}'[v]",
        "-map", "[v]",
        "-map", "1:a",
        "-shortest",
        "-c:v", "libx264", "-preset", "fast", "-crf", "22",
        "-c:a", "aac", "-b:a", "192k",
        str(output_path),
    ]

    proc = subprocess.run(cmd, capture_output=True, text=True)

    if proc.returncode != 0:
        raise RuntimeError(
            f"ffmpeg falhou (code {proc.returncode}):\n{proc.stderr[-2000:]}"
        )

    return output_path
