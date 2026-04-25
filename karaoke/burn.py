"""Gera video karaoke: fundo preto + audio + legenda queimada via ffmpeg."""

import shutil
import subprocess
from pathlib import Path


def burn(
    audio_path: str | Path,
    subtitle_path: str | Path,
    output_path: str | Path,
    resolution: tuple[int, int] = (1280, 720),
    fps: int = 30,
    overwrite: bool = True,
) -> Path:
    """Combina audio e legenda em video MP4 com fundo preto.

    Aceita .ass ou .srt como subtitle_path.

    Args:
        audio_path:     caminho para o audio (no_vocals.mp3)
        subtitle_path:  caminho para o arquivo de legenda (.ass ou .srt)
        output_path:    caminho do video de saida (.mp4)
        resolution:     (largura, altura) em pixels
        fps:            frames por segundo do video
        overwrite:      sobrescrever se ja existir

    Retorna:
        Path do video gerado
    """
    if not shutil.which("ffmpeg"):
        raise RuntimeError("ffmpeg nao encontrado no PATH. Instale: sudo apt install ffmpeg")

    audio_path    = Path(audio_path)
    subtitle_path = Path(subtitle_path)
    output_path   = Path(output_path)

    if not audio_path.is_file():
        raise FileNotFoundError(f"Audio nao encontrado: {audio_path}")
    if not subtitle_path.is_file():
        raise FileNotFoundError(f"Legenda nao encontrada: {subtitle_path}")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    w, h = resolution

    # Path absoluto — ffmpeg precisa disso para o filtro ass/subtitles
    sub_abs = str(subtitle_path.resolve()).replace("\\", "/")

    # O filtro 'ass' nativo do ffmpeg aceita .ass diretamente com estilos proprios.
    # Para .srt, usa 'subtitles' com force_style.
    if subtitle_path.suffix.lower() == ".ass":
        vf = f"ass='{sub_abs}'"
    else:
        font_size = max(18, h // 25)
        style = (
            f"FontSize={font_size},FontName=Arial,"
            "PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,"
            "Outline=2,Shadow=1,Alignment=2,MarginV=40"
        )
        sub_esc = sub_abs.replace(":", "\\:")
        vf = f"subtitles='{sub_esc}':force_style='{style}'"

    cmd = [
        "ffmpeg",
        *([ "-y"] if overwrite else []),
        "-f", "lavfi",
        "-i", f"color=c=black:s={w}x{h}:r={fps}",
        "-i", str(audio_path),
        "-filter_complex", f"[0:v]{vf}[v]",
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
