"""Converte segmentos com timestamps para formato SRT."""

from pathlib import Path


def to_srt(segments: list[dict]) -> str:
    """Converte lista de segmentos para string no formato SRT."""
    segments = _sanitize(segments)
    parts = []
    for i, seg in enumerate(segments, start=1):
        parts.append(
            f"{i}\n"
            f"{_fmt_time(seg['start'])} --> {_fmt_time(seg['end'])}\n"
            f"{seg['text'].strip()}\n"
        )
    return "\n".join(parts)


def write_srt(segments: list[dict], path: str | Path) -> Path:
    """Escreve arquivo .srt no disco e retorna o Path."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(to_srt(segments), encoding="utf-8")
    return path


# ── helpers ───────────────────────────────────────────────────────────────────

def _fmt_time(seconds: float) -> str:
    seconds = max(0.0, seconds)
    ms  = int(round((seconds % 1) * 1000))
    s   = int(seconds) % 60
    m   = (int(seconds) // 60) % 60
    h   = int(seconds) // 3600
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _sanitize(segments: list[dict]) -> list[dict]:
    result = []
    for seg in segments:
        start = float(seg["start"])
        end   = float(seg["end"])
        if end <= start:
            end = start + 2.0
        result.append({"text": seg["text"], "start": start, "end": end})

    # Garantir que segmentos nao se sobreponham
    for i in range(len(result) - 1):
        if result[i]["end"] > result[i + 1]["start"]:
            result[i]["end"] = max(result[i]["start"] + 0.1, result[i + 1]["start"] - 0.05)

    return result
