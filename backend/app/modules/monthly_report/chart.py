"""Generare chart-uri PNG cu PIL (fără matplotlib).

Chart-uri suportate:
- horizontal_bar_chart (grupuri curr vs prev)
- comparison_bars (2 branduri, 2 ani — layout rapoartele RAF)
- donut_chart (pondere % cu legenda laterală)
- evolution_lines (linii lunare curr vs prev)
"""
from __future__ import annotations

import io
import math
from dataclasses import dataclass

from PIL import Image, ImageDraw, ImageFont


@dataclass
class BarRow:
    label: str
    current: float
    prev: float


def _font(size: int) -> ImageFont.ImageFont:
    for p in (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ):
        try:
            return ImageFont.truetype(p, size)
        except Exception:
            continue
    return ImageFont.load_default()


def _fmt_short(v: float) -> str:
    if abs(v) >= 1_000_000:
        return f"{v/1_000_000:.2f}M"
    if abs(v) >= 1_000:
        return f"{v/1_000:.0f}k"
    return f"{v:.0f}"


def _fmt_ron(v: float) -> str:
    return f"{v:,.0f}".replace(",", ".") + " RON"


def horizontal_bar_chart(
    rows: list[BarRow],
    *,
    label_current: str = "An curent",
    label_prev: str = "An anterior",
    title: str = "",
    width: int = 1200,
    row_h: int = 40,
) -> bytes:
    """Bare orizontale grouped (2 pe rând: curent deasupra, anterior sub)."""
    if not rows:
        rows = [BarRow(label="(fără date)", current=0, prev=0)]

    padding_top = 56 if title else 34
    padding_bottom = 24
    padding_left = 170
    padding_right = 140

    height = padding_top + padding_bottom + len(rows) * row_h
    img = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(img)

    font_title = _font(18)
    font_label = _font(12)
    font_value = _font(11)

    if title:
        draw.text((padding_left, 14), title, fill="#0f172a", font=font_title)

    max_val = max(
        max((r.current for r in rows), default=0),
        max((r.prev for r in rows), default=0),
        1.0,
    )
    chart_w = width - padding_left - padding_right
    bar_h = int(row_h * 0.40)
    gap = 3

    legend_y = padding_top - 22
    draw.rectangle([padding_left, legend_y, padding_left + 14, legend_y + 12], fill="#2563eb")
    draw.text((padding_left + 20, legend_y - 2), label_current, fill="#111827", font=font_label)
    lx = padding_left + 170
    draw.rectangle([lx, legend_y, lx + 14, legend_y + 12], fill="#94a3b8")
    draw.text((lx + 20, legend_y - 2), label_prev, fill="#111827", font=font_label)

    for i, r in enumerate(rows):
        y = padding_top + i * row_h
        draw.text((8, y + bar_h - 2), r.label[:22], fill="#111827", font=font_label)
        w_cur = max(2, int((r.current / max_val) * chart_w))
        draw.rectangle([padding_left, y, padding_left + w_cur, y + bar_h], fill="#2563eb")
        draw.text(
            (padding_left + w_cur + 6, y + 1), _fmt_short(r.current),
            fill="#111827", font=font_value,
        )
        y2 = y + bar_h + gap
        w_prev = max(2, int((r.prev / max_val) * chart_w))
        draw.rectangle([padding_left, y2, padding_left + w_prev, y2 + bar_h], fill="#94a3b8")
        draw.text(
            (padding_left + w_prev + 6, y2 + 1), _fmt_short(r.prev),
            fill="#475569", font=font_value,
        )

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def comparison_bars(
    *,
    title: str,
    series: list[tuple[str, float, float, str]],  # (label, current, prev, color)
    label_current: str,
    label_prev: str,
    width: int = 1200,
    height: int = 420,
) -> bytes:
    """Bare verticale — fiecare 'series' e un grup (ex: Adeplast, Sika, Total).
    Pentru fiecare grup: bara curent + bara anterior, cu valori deasupra.
    """
    img = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(img)
    font_title = _font(18)
    font_label = _font(13)
    font_value = _font(12)

    draw.text((40, 14), title, fill="#0f172a", font=font_title)

    # Legendă
    ly = 44
    draw.rectangle([40, ly, 54, ly + 12], fill="#2563eb")
    draw.text((62, ly - 2), label_current, fill="#111827", font=font_label)
    draw.rectangle([180, ly, 194, ly + 12], fill="#94a3b8")
    draw.text((202, ly - 2), label_prev, fill="#111827", font=font_label)

    pad_l, pad_r = 60, 40
    pad_t, pad_b = 80, 48
    chart_w = width - pad_l - pad_r
    chart_h = height - pad_t - pad_b
    n = max(1, len(series))
    group_w = chart_w / n
    bar_w = int(group_w * 0.28)
    bar_gap = 8

    max_val = max([s[1] for s in series] + [s[2] for s in series] + [1.0])

    for i, (label, cur, prev, color) in enumerate(series):
        gx = pad_l + int(i * group_w + group_w / 2)
        # Bara curent (accentuat cu culoarea seriei)
        cur_h = int((cur / max_val) * chart_h)
        prev_h = int((prev / max_val) * chart_h)
        draw.rectangle(
            [gx - bar_w - bar_gap // 2, pad_t + chart_h - cur_h, gx - bar_gap // 2, pad_t + chart_h],
            fill=color,
        )
        draw.rectangle(
            [gx + bar_gap // 2, pad_t + chart_h - prev_h, gx + bar_w + bar_gap // 2, pad_t + chart_h],
            fill="#94a3b8",
        )
        # Valori deasupra
        vc = _fmt_short(cur)
        draw.text(
            (gx - bar_w - bar_gap // 2, pad_t + chart_h - cur_h - 16),
            vc, fill="#0f172a", font=font_value,
        )
        vp = _fmt_short(prev)
        draw.text(
            (gx + bar_gap // 2, pad_t + chart_h - prev_h - 16),
            vp, fill="#475569", font=font_value,
        )
        # Label sub grup
        draw.text((gx - 40, pad_t + chart_h + 8), label[:20], fill="#111827", font=font_label)

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def donut_chart(
    *,
    title: str,
    segments: list[tuple[str, float, str]],  # (label, value, color)
    width: int = 900,
    height: int = 360,
) -> bytes:
    """Donut cu legenda la dreapta. Fiecare segment → arc proporțional."""
    img = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(img)
    font_title = _font(16)
    font_lg = _font(12)

    draw.text((40, 14), title, fill="#0f172a", font=font_title)

    total = sum(max(0, v) for _, v, _ in segments) or 1.0
    cx, cy = 180, height // 2 + 10
    r_out, r_in = 120, 70

    start = -90.0
    for label, v, color in segments:
        if v <= 0:
            continue
        sweep = (v / total) * 360.0
        end = start + sweep
        draw.pieslice([cx - r_out, cy - r_out, cx + r_out, cy + r_out],
                      start, end, fill=color)
        start = end
    # Mascare interior pentru donut
    draw.ellipse([cx - r_in, cy - r_in, cx + r_in, cy + r_in], fill="white")

    # Legenda
    lx, ly = 360, 70
    for label, v, color in segments:
        pct = v / total * 100 if total > 0 else 0
        draw.rectangle([lx, ly, lx + 14, ly + 14], fill=color)
        draw.text((lx + 22, ly - 1),
                  f"{label}  —  {_fmt_ron(v)}  ({pct:.1f}%)",
                  fill="#111827", font=font_lg)
        ly += 28

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def evolution_lines(
    *,
    title: str,
    months: list[int],
    series: list[tuple[str, list[float], str]],  # (label, values, color)
    width: int = 1200,
    height: int = 360,
) -> bytes:
    """Linii evoluție pe luni. Fiecare serie = o linie colorată cu label."""
    img = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(img)
    font_title = _font(18)
    font_label = _font(12)
    font_val = _font(10)

    draw.text((40, 14), title, fill="#0f172a", font=font_title)

    pad_l, pad_r = 70, 40
    pad_t, pad_b = 60, 50
    chart_w = width - pad_l - pad_r
    chart_h = height - pad_t - pad_b

    # Legenda
    lx, ly = pad_l, 40
    for label, _, color in series:
        draw.rectangle([lx, ly, lx + 14, ly + 12], fill=color)
        draw.text((lx + 20, ly - 2), label, fill="#111827", font=font_label)
        lx += 160

    max_val = max(max(v) for _, v, _ in series) if series else 1.0
    max_val = max(max_val, 1.0)
    n = max(1, len(months))
    step_x = chart_w / max(1, n - 1) if n > 1 else chart_w

    # Axa X
    draw.line([pad_l, pad_t + chart_h, pad_l + chart_w, pad_t + chart_h], fill="#cbd5e1")
    for i, m in enumerate(months):
        x = pad_l + int(i * step_x) if n > 1 else pad_l + chart_w // 2
        draw.text((x - 8, pad_t + chart_h + 6),
                  ["Ian","Feb","Mar","Apr","Mai","Iun","Iul","Aug","Sep","Oct","Noi","Dec"][m - 1],
                  fill="#475569", font=font_label)

    for label, values, color in series:
        pts = []
        for i, v in enumerate(values):
            x = pad_l + int(i * step_x) if n > 1 else pad_l + chart_w // 2
            y = pad_t + chart_h - int((v / max_val) * chart_h)
            pts.append((x, y))
        if len(pts) >= 2:
            draw.line(pts, fill=color, width=3)
        for i, (x, y) in enumerate(pts):
            draw.ellipse([x - 4, y - 4, x + 4, y + 4], fill=color)
            draw.text((x - 18, y - 18), _fmt_short(values[i]),
                      fill=color, font=font_val)

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


__all__ = [
    "BarRow",
    "horizontal_bar_chart",
    "comparison_bars",
    "donut_chart",
    "evolution_lines",
]
