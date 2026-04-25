"""Alinha linhas de letra original aos timestamps de segmentos transcritos."""

import re
import unicodedata


def align(
    segments: list[dict],
    lyrics: str,
    threshold: float = 0.05,
) -> list[dict]:
    """Alinha letra original aos timestamps da transcricao.

    Retorna lista de segmentos usando o texto ORIGINAL da letra com
    os timestamps derivados da transcricao via programacao dinamica.

    Args:
        segments: saida de transcribe() — [{"text", "start", "end"}]
        lyrics:   letra original colada pelo usuario
        threshold: similaridade minima para considerar um match

    Retorna:
        [{"text": str, "start": float, "end": float}, ...]
    """
    lines = _parse_lyrics(lyrics)
    if not lines:
        return segments
    if not segments:
        return _distribute_evenly(lines, 0.0, 0.0)

    cost = _build_cost_matrix(lines, segments)
    mapping = _dp_align(cost, len(lines), len(segments))
    return _resolve_timestamps(lines, segments, mapping)


# ── parsing ───────────────────────────────────────────────────────────────────

def _parse_lyrics(text: str) -> list[str]:
    lines = []
    for line in text.splitlines():
        line = line.strip()
        if line:
            lines.append(line)
    return lines


# ── normalizacao e similaridade ───────────────────────────────────────────────

def _normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    text = re.sub(r"[^\w\s]", "", text).lower()
    return re.sub(r"\s+", " ", text).strip()


def _word_bigrams(text: str) -> frozenset:
    words = _normalize(text).split()
    if len(words) < 2:
        return frozenset((w,) for w in words)
    return frozenset((words[i], words[i + 1]) for i in range(len(words) - 1))


def _similarity(a: str, b: str) -> float:
    ba = _word_bigrams(a)
    bb = _word_bigrams(b)
    if not ba and not bb:
        return 1.0
    if not ba or not bb:
        return 0.0
    return len(ba & bb) / len(ba | bb)


# ── matriz de custo ───────────────────────────────────────────────────────────

def _build_cost_matrix(lines: list[str], segments: list[dict]) -> list[list[float]]:
    return [
        [1.0 - _similarity(line, seg["text"]) for seg in segments]
        for line in lines
    ]


# ── DP monotonica ─────────────────────────────────────────────────────────────

_INF = float("inf")
_SKIP_PENALTY = 0.4  # custo de pular um segmento do Whisper sem usar


def _dp_align(cost: list[list[float]], L: int, S: int) -> list[int | None]:
    """Retorna mapping[i] = indice do segmento para a linha i (ou None)."""

    # dp[i][j] = custo minimo para alinhar linhas[0..i] com segmentos[0..j]
    dp   = [[_INF] * (S + 1) for _ in range(L + 1)]
    back = [[None] * (S + 1) for _ in range(L + 1)]

    dp[0][0] = 0.0

    for j in range(1, S + 1):
        dp[0][j] = dp[0][j - 1] + _SKIP_PENALTY  # pular segmentos iniciais
        back[0][j] = (0, j - 1)

    for i in range(1, L + 1):
        for j in range(1, S + 1):
            options = [
                (dp[i - 1][j - 1] + cost[i - 1][j - 1], (i - 1, j - 1)),  # match 1:1
                (dp[i - 1][j]     + cost[i - 1][j - 1], (i - 1, j)),       # mult linhas -> mesmo seg
                (dp[i][j - 1]     + _SKIP_PENALTY,       (i,     j - 1)),   # pula segmento
            ]
            best_cost, best_back = min(options, key=lambda x: x[0])
            dp[i][j] = best_cost
            back[i][j] = best_back

    # traceback
    seg_assignment: list[int | None] = [None] * L
    i, j = L, S
    while i > 0:
        bi, bj = back[i][j]
        if bi == i - 1 and bj == j - 1:
            seg_assignment[i - 1] = j - 1  # match
        elif bi == i - 1 and bj == j:
            seg_assignment[i - 1] = j - 1  # multi-linha no mesmo segmento
        # else: segmento pulado, linha sem assignment
        i, j = bi, bj

    return seg_assignment


# ── resolucao de timestamps ───────────────────────────────────────────────────

def _resolve_timestamps(
    lines: list[str],
    segments: list[dict],
    mapping: list[int | None],
) -> list[dict]:
    result: list[dict] = []

    # Agrupar linhas que mapeiam para o mesmo segmento
    i = 0
    while i < len(lines):
        seg_idx = mapping[i]

        if seg_idx is None:
            # Linha sem correspondencia: interpola
            start, end = _interpolate(i, mapping, segments, result)
            result.append({"text": lines[i], "start": start, "end": end})
            i += 1
            continue

        # Coletar todas as linhas consecutivas com o mesmo segmento
        group = [i]
        j = i + 1
        while j < len(lines) and mapping[j] == seg_idx:
            group.append(j)
            j += 1

        seg = segments[seg_idx]
        duration = seg["end"] - seg["start"]
        n = len(group)

        for k, line_idx in enumerate(group):
            start = seg["start"] + duration * k / n
            end   = seg["start"] + duration * (k + 1) / n
            result.append({"text": lines[line_idx], "start": start, "end": end})

        i = j

    return result


def _interpolate(
    line_idx: int,
    mapping: list[int | None],
    segments: list[dict],
    already_resolved: list[dict],
) -> tuple[float, float]:
    # Pega o timestamp do ultimo segmento resolvido como ancora inicial
    prev_end = already_resolved[-1]["end"] if already_resolved else 0.0

    # Procura o proximo segmento mapeado
    next_start = None
    for k in range(line_idx + 1, len(mapping)):
        idx = mapping[k]
        if idx is not None:
            next_start = segments[idx]["start"]
            break

    if next_start is None:
        # Nao ha proximo — usa 2s apos o anterior
        return prev_end, prev_end + 2.0

    # Divide o intervalo entre prev_end e next_start
    gap = next_start - prev_end
    return prev_end, prev_end + max(gap / 2, 1.0)


def _distribute_evenly(lines: list[str], start: float, end: float) -> list[dict]:
    if not lines:
        return []
    # Sem segmentos: distribui 3s por linha a partir de start=0
    result = []
    t = start if start > 0 else 0.0
    for line in lines:
        result.append({"text": line, "start": t, "end": t + 3.0})
        t += 3.0
    return result
