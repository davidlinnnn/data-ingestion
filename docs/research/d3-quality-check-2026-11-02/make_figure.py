"""#153 report figure: test AUROC with page-bootstrap 95% intervals, per category and model.

    python3 docs/research/d3-quality-check-2026-11-02/make_figure.py

Reads metrics/d3-{nano,mini,flash}.json next to this file and writes auroc-test.svg. The SVG
carries its own white background so it reads the same in light and dark viewers.
"""

import json
from pathlib import Path

HERE = Path(__file__).parent
MODELS = [("d3-nano", "#2a78d6"), ("d3-mini", "#eb6834"), ("d3-flash", "#1baf7a")]
CATEGORIES = [
    ("formula", "formula"),
    ("table", "table"),
    ("ocr", "picture-ocr"),
    ("description", "description"),
    ("figure_type", "figure_type *"),
    ("chart", "chart *"),
]
W, LEFT, RIGHT, TOP, ROW, BOTTOM = 760, 130, 24, 44, 46, 46
X0, X1 = 0.25, 1.0


def x(v: float) -> float:
    return LEFT + (v - X0) / (X1 - X0) * (W - LEFT - RIGHT)


def main() -> None:
    metrics = {
        m: json.loads((HERE / "metrics" / f"{m}.json").read_text())["models"][m] for m, _ in MODELS
    }
    height = TOP + len(CATEGORIES) * ROW + BOTTOM
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {height}" width="{W}" '
        f'height="{height}" font-family="Helvetica, Arial, sans-serif">',
        f'<rect width="{W}" height="{height}" fill="#ffffff"/>',
    ]
    for i, (name, color) in enumerate(MODELS):
        lx = LEFT + i * 110
        out.append(f'<circle cx="{lx + 6}" cy="18" r="5" fill="{color}"/>')
        out.append(f'<text x="{lx + 16}" y="22" font-size="13" fill="#14171c">{name}</text>')
    bottom = TOP + len(CATEGORIES) * ROW
    for i in range(0, len(CATEGORIES), 2):
        y = TOP + i * ROW
        out.append(
            f'<rect x="{LEFT}" y="{y}" width="{W - LEFT - RIGHT}" height="{ROW}" fill="#eef2f7"/>'
        )
    for v in [0.3, 0.4, 0.5, 0.6, 0.7, 0.75, 0.8, 0.9, 1.0]:
        ref = v in (0.5, 0.75)
        dash = ' stroke-dasharray="4 3"' if ref else ""
        out.append(
            f'<line x1="{x(v):.1f}" x2="{x(v):.1f}" y1="{TOP}" y2="{bottom}" '
            f'stroke="{"#6c7480" if ref else "#dfe3e8"}" stroke-width="{1.5 if ref else 1}"{dash}/>'
        )
        label = f"{v:.2f}" if v == 0.75 else f"{v:.1f}"
        out.append(
            f'<text x="{x(v):.1f}" y="{bottom + 16}" font-size="11.5" fill="#6c7480" '
            f'text-anchor="middle">{label}</text>'
        )
    for v, label in [(0.5, "chance"), (0.75, "C2 bar")]:
        out.append(
            f'<text x="{x(v):.1f}" y="{bottom + 34}" font-size="11.5" fill="#4a515c" '
            f'text-anchor="middle">{label}</text>'
        )
    for i, (key, label) in enumerate(CATEGORIES):
        cy = TOP + i * ROW + ROW / 2
        out.append(
            f'<text x="{LEFT - 10}" y="{cy + 4:.1f}" font-size="13" fill="#14171c" '
            f'text-anchor="end">{label}</text>'
        )
        for j, (m, color) in enumerate(MODELS):
            d = metrics[m][key]
            v = d["AUROC_raw"]
            lo, hi = d["AUROC_CI"]["interval"]
            y = cy + (j - 1) * 11
            out.append(
                f'<line x1="{x(lo):.1f}" x2="{x(hi):.1f}" y1="{y:.1f}" y2="{y:.1f}" '
                f'stroke="{color}" stroke-width="2" stroke-linecap="round"/>'
            )
            out.append(
                f'<circle cx="{x(v):.1f}" cy="{y:.1f}" r="4.5" fill="{color}" '
                f'stroke="#ffffff" stroke-width="2"><title>{label} {m}: {v:.3f} '
                f"({lo:.3f}-{hi:.3f})</title></circle>"
            )
    out.append("</svg>")
    (HERE / "auroc-test.svg").write_text("\n".join(out) + "\n")


if __name__ == "__main__":
    main()
