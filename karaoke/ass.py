"""Gera arquivo .ass (Advanced SubStation Alpha) com bloco de 3 linhas.

Layout karaoke (de baixo pra cima):
  - Proxima linha:  cinza, menor   (o que vem a seguir)
  - Linha atual:    branca, maior  (o que esta sendo cantado)
  - Linha anterior: cinza, menor   (contexto do que passou)

Cada estilo tem seu proprio MarginV — sem override de \pos, sem sobreposicao.
Gaps curtos entre segmentos sao preenchidos para evitar piscar.
"""

from pathlib import Path

# Gaps menores que isso sao preenchidos (legenda nao pisca)
_FLICKER_THRESHOLD = 1.5  # segundos


def to_ass(
    segments: list[dict],
    resolution: tuple[int, int] = (1280, 720),
) -> str:
    """Converte segmentos para string no formato ASS com bloco de 3 linhas."""
    w, h = resolution

    font_main = max(28, h // 16)   # ~45px em 720p — bem legivel
    font_ctx  = max(20, h // 24)   # ~30px em 720p

    # Altura aproximada de cada linha (fontsize * 1.5 para incluir leading)
    lh_main = int(font_main * 1.5)
    lh_ctx  = int(font_ctx  * 1.5)
    spacing = max(8, h // 80)
    base_v  = max(40, h // 16)     # margem do fundo

    # MarginV de cada estilo = distancia do fundo ate a base do texto
    # Ordem de baixo pra cima: Next → Main → Prev
    margin_next = base_v
    margin_main = base_v + lh_ctx  + spacing
    margin_prev = base_v + lh_ctx  + spacing + lh_main + spacing

    header = _header(w, h, font_main, font_ctx, margin_prev, margin_main, margin_next)
    events = _build_events(segments)
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


# ── header ────────────────────────────────────────────────────────────────────

def _header(
    w: int, h: int,
    font_main: int, font_ctx: int,
    margin_prev: int, margin_main: int, margin_next: int,
) -> str:
    fmt = "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding"
    # Cores: AABBGGRR (ASS usa BGR)
    white  = "&H00FFFFFF"
    grey   = "&H00999999"
    black  = "&H00000000"
    transp = "&H00000000"
    def style(name, size, color, bold, outline, margin):
        return f"Style: {name},Arial,{size},{color},&H000000FF,{black},{transp},{bold},0,0,0,100,100,0,0,1,{outline},1,2,40,40,{margin},1"

    return (
        f"[Script Info]\n"
        f"ScriptType: v4.00+\n"
        f"PlayResX: {w}\n"
        f"PlayResY: {h}\n"
        f"Collisions: Normal\n"
        f"WrapStyle: 1\n\n"
        f"[V4+ Styles]\n"
        f"{fmt}\n"
        f"{style('Main', font_main, white, -1, 2,   margin_main)}\n"
        f"{style('Prev', font_ctx,  grey,   0, 1, margin_prev)}\n"
        f"{style('Next', font_ctx,  grey,   0, 1, margin_next)}\n\n"
        f"[Events]\n"
        f"Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
    )


# ── eventos ───────────────────────────────────────────────────────────────────

def _build_events(segments: list[dict]) -> str:
    if not segments:
        return ""

    n     = len(segments)
    lines = []

    for i, seg in enumerate(segments):
        t_start = seg["start"]

        # Estende o fim ate o inicio do proximo se o gap for curto
        if i < n - 1:
            gap = segments[i + 1]["start"] - seg["end"]
            t_end = segments[i + 1]["start"] if gap < _FLICKER_THRESHOLD else seg["end"]
        else:
            t_end = seg["end"]

        # Linha atual
        lines.append(f"Dialogue: 1,{_t(t_start)},{_t(t_end)},Main,,0,0,0,,{_esc(seg['text'])}")

        # Linha anterior (acima da atual)
        if i > 0:
            lines.append(f"Dialogue: 0,{_t(t_start)},{_t(t_end)},Prev,,0,0,0,,{_esc(segments[i-1]['text'])}")

        # Proxima linha (abaixo da atual)
        if i < n - 1:
            lines.append(f"Dialogue: 0,{_t(t_start)},{_t(t_end)},Next,,0,0,0,,{_esc(segments[i+1]['text'])}")

    return "\n".join(lines) + "\n"


# ── helpers ───────────────────────────────────────────────────────────────────

def _t(seconds: float) -> str:
    seconds = max(0.0, seconds)
    cs = int(round((seconds % 1) * 100))
    s  = int(seconds) % 60
    m  = (int(seconds) // 60) % 60
    h  = int(seconds) // 3600
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def _esc(text: str) -> str:
    return text.replace("{", "\\{").replace("}", "\\}")
