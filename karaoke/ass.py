"""Gera arquivo .ass (Advanced SubStation Alpha) com bloco de 3 linhas.

Layout (centralizado verticalmente):
  - Linha anterior: cinza claro  (o que acabou de ser cantado)
  - Linha atual:    branca/bold   (o que esta sendo cantado agora)
  - Proxima linha:  cinza claro   (o que vem a seguir)

Sem tela preta:
  - Gaps curtos (< 1.5s): evento estendido ate o proximo inicio
  - Gaps longos: mostrar linha anterior e proxima em cinza
  - Antes da primeira frase: proxima em cinza
  - Apos a ultima frase: ultima em cinza por alguns segundos
"""

from pathlib import Path

_FLICKER_THRESHOLD = 1.5   # segundos — gaps menores sao preenchidos
_TRAIL_SECONDS     = 5.0   # segundos que a ultima linha fica cinza apos acabar


def to_ass(
    segments: list[dict],
    resolution: tuple[int, int] = (1280, 720),
) -> str:
    w, h = resolution

    font_main = max(36, h // 14)   # ~51px em 720p
    font_ctx  = max(24, h // 22)   # ~33px em 720p

    # Altura de linha estimada (fontsize * 1.4 para incluir leading)
    lh_main = int(font_main * 1.4)
    lh_ctx  = int(font_ctx  * 1.4)
    spacing = max(10, h // 60)

    # Posicoes Y absolutas para cada linha (bloco centrado em h/2)
    cy      = h // 2
    cx      = w // 2
    main_y  = cy
    prev_y  = cy - lh_main // 2 - spacing - lh_ctx // 2
    next_y  = cy + lh_main // 2 + spacing + lh_ctx // 2

    header = _header(w, h, font_main, font_ctx)
    events = _build_events(segments, cx, main_y, prev_y, next_y)
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

def _header(w: int, h: int, font_main: int, font_ctx: int) -> str:
    fmt = (
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, "
        "OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, "
        "ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
        "Alignment, MarginL, MarginR, MarginV, Encoding"
    )
    # Cores no formato ASS: &HAABBGGRR
    white = "&H00FFFFFF"
    grey  = "&H00AAAAAA"
    black = "&H00000000"
    transp = "&H00000000"

    def style(name, size, color, bold, outline):
        # Alignment=5 = centro-centro; \pos() nos eventos posiciona cada linha
        return (
            f"Style: {name},Arial,{size},{color},&H000000FF,"
            f"{black},{transp},{bold},0,0,0,100,100,0,0,1,{outline},1,"
            f"5,0,0,0,1"
        )

    return (
        f"[Script Info]\n"
        f"ScriptType: v4.00+\n"
        f"PlayResX: {w}\n"
        f"PlayResY: {h}\n"
        f"Collisions: Normal\n"
        f"WrapStyle: 1\n\n"
        f"[V4+ Styles]\n"
        f"{fmt}\n"
        f"{style('Main', font_main, white, -1, 2)}\n"
        f"{style('Ctx',  font_ctx,  grey,   0, 1)}\n\n"
        f"[Events]\n"
        f"Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
    )


# ── eventos ───────────────────────────────────────────────────────────────────

def _build_events(
    segments: list[dict],
    cx: int, main_y: int, prev_y: int, next_y: int,
) -> str:
    if not segments:
        return ""

    n      = len(segments)
    events: list[str] = []

    def main_line(t0, t1, text):
        return _dlg(2, t0, t1, "Main", cx, main_y, text)

    def prev_line(t0, t1, text):
        return _dlg(1, t0, t1, "Ctx", cx, prev_y, text)

    def next_line(t0, t1, text):
        return _dlg(1, t0, t1, "Ctx", cx, next_y, text)

    # Antes da primeira frase: mostra ela em cinza como "proxima"
    if segments[0]["start"] > 0.3:
        events.append(next_line(0.0, segments[0]["start"], segments[0]["text"]))

    for i, seg in enumerate(segments):
        t_start = seg["start"]
        has_next = i < n - 1

        if has_next:
            gap = segments[i + 1]["start"] - seg["end"]
            # Gap curto: estende evento ate o inicio do proximo (sem piscar)
            t_end = segments[i + 1]["start"] if gap < _FLICKER_THRESHOLD else seg["end"]
        else:
            gap   = 999.0
            t_end = seg["end"]

        # Bloco ativo: linha atual branca + contexto cinza
        events.append(main_line(t_start, t_end, seg["text"]))
        if i > 0:
            events.append(prev_line(t_start, t_end, segments[i - 1]["text"]))
        if has_next:
            events.append(next_line(t_start, t_end, segments[i + 1]["text"]))

        # Gap longo: preenche com cinza (sem linha branca)
        if has_next and gap >= _FLICKER_THRESHOLD:
            gap_s = seg["end"]
            gap_e = segments[i + 1]["start"]
            events.append(prev_line(gap_s, gap_e, seg["text"]))
            events.append(next_line(gap_s, gap_e, segments[i + 1]["text"]))

    # Apos a ultima frase: mostra ela em cinza por alguns segundos
    last = segments[-1]
    events.append(prev_line(last["end"], last["end"] + _TRAIL_SECONDS, last["text"]))

    return "\n".join(events) + "\n"


# ── helpers ───────────────────────────────────────────────────────────────────

def _dlg(layer: int, t0: float, t1: float, style: str, x: int, y: int, text: str) -> str:
    # \an5 = centro-centro; \pos(x,y) posiciona o centro do texto
    return (
        f"Dialogue: {layer},{_t(t0)},{_t(t1)},{style},,0,0,0,,"
        f"{{\\an5\\pos({x},{y})}}{_esc(text)}"
    )


def _t(seconds: float) -> str:
    seconds = max(0.0, seconds)
    cs = int(round((seconds % 1) * 100))
    s  = int(seconds) % 60
    m  = (int(seconds) // 60) % 60
    h  = int(seconds) // 3600
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def _esc(text: str) -> str:
    return text.replace("{", "\\{").replace("}", "\\}")
