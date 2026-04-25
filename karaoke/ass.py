"""Gera arquivo .ass (Advanced SubStation Alpha) com bloco de 3 linhas.

Layout karaoke:
  - Linha anterior: cinza, menor        (contexto do que passou)
  - Linha atual:    branca, maior        (o que esta sendo cantado)
  - Proxima linha:  cinza, menor         (o que vem a seguir)

O bloco inteiro e atualizado a cada nova linha ativa.
"""

from pathlib import Path


def to_ass(
    segments: list[dict],
    resolution: tuple[int, int] = (1280, 720),
) -> str:
    """Converte segmentos para string no formato ASS com bloco de 3 linhas."""
    w, h = resolution
    font_size_main = max(22, h // 22)
    font_size_ctx  = max(16, h // 32)
    margin_v       = max(30, h // 18)

    header = _header(w, h, font_size_main, font_size_ctx, margin_v)
    events = _build_events(segments, font_size_main, font_size_ctx)
    return header + events


def write_ass(
    segments: list[dict],
    path: str | Path,
    resolution: tuple[int, int] = (1280, 720),
) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(to_ass(segments, resolution), encoding="utf-8-sig")
    return path


# ── header ASS ────────────────────────────────────────────────────────────────

def _header(w: int, h: int, font_main: int, font_ctx: int, margin_v: int) -> str:
    return f"""\
[Script Info]
ScriptType: v4.00+
PlayResX: {w}
PlayResY: {h}
Collisions: Normal
WrapStyle: 1

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Main,Arial,{font_main},&H00FFFFFF,&H000000FF,&H00000000,&H96000000,-1,0,0,0,100,100,0,0,1,2,1,2,40,40,{margin_v},1
Style: Ctx,Arial,{font_ctx},&H00888888,&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,1,0,2,40,40,{margin_v + font_main + 8},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


# ── construcao dos eventos ────────────────────────────────────────────────────

def _build_events(segments: list[dict], font_main: int, font_ctx: int) -> str:
    if not segments:
        return ""

    lines: list[str] = []
    n = len(segments)

    for i, seg in enumerate(segments):
        t_start = seg["start"]
        t_end   = seg["end"]

        # Linha atual (Main): visivel durante todo o segmento
        lines.append(
            f"Dialogue: 0,{_t(t_start)},{_t(t_end)},Main,,0,0,0,,{_esc(seg['text'])}"
        )

        # Linha anterior (Ctx, layer 0, position acima da Main)
        if i > 0:
            prev = segments[i - 1]
            lines.append(
                f"Dialogue: 0,{_t(t_start)},{_t(t_end)},Ctx,,0,0,0,"
                f",{{\\an2\\pos({_cx(font_main, font_ctx, 'prev', 1280, 720)})}}"
                f"{_esc(prev['text'])}"
            )

        # Proxima linha (Ctx, abaixo da Main)
        if i < n - 1:
            nxt = segments[i + 1]
            lines.append(
                f"Dialogue: 0,{_t(t_start)},{_t(t_end)},Ctx,,0,0,0,"
                f",{{\\an2\\pos({_cx(font_main, font_ctx, 'next', 1280, 720)})}}"
                f"{_esc(nxt['text'])}"
            )

    return "\n".join(lines) + "\n"


def _cx(font_main: int, font_ctx: int, which: str, w: int, h: int) -> str:
    """Calcula posicao X,Y para linhas de contexto."""
    cx = w // 2
    margin_v = max(30, h // 18)

    # Main fica em Alignment=2 (centro-baixo) com MarginV padrao.
    # Ctx 'prev' fica acima da Main; 'next' fica abaixo.
    if which == "prev":
        y = h - margin_v - font_main - 12 - font_ctx
    else:
        y = h - margin_v + 8

    return f"{cx},{y}"


def _t(seconds: float) -> str:
    seconds = max(0.0, seconds)
    cs  = int(round((seconds % 1) * 100))
    s   = int(seconds) % 60
    m   = (int(seconds) // 60) % 60
    h   = int(seconds) // 3600
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def _esc(text: str) -> str:
    """Escapa caracteres especiais ASS."""
    return text.replace("{", "\\{").replace("}", "\\}")
