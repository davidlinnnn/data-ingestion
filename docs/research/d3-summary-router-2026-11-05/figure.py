"""curve.svg: the test skip-rate curve from metrics.json, plus the natural LLM flags still routed.

    .venv/bin/python docs/research/d3-summary-router-2026-11-05/figure.py OUT

Plain SVG (no plotting dependency). The still-routed line is computed here from OUT's units and
the test scores; metrics.json registers it at t_route and t_route_alt only.
"""

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
W, H, L, R, T, B = 760, 450, 60, 200, 62, 56
SURFACE, GRID, INK, MUTED = "#fcfcfb", "#e6e5e1", "#0b0b0b", "#52514e"
SERIES = [("d3_recall", "d3 recall (planted)", "#2a78d6"),
          ("overall_catch", "overall catch (planted)", "#eb6834"),
          ("still_routed", "natural LLM flags still sent", "#1baf7a")]  # fmt: skip


def x(v: float) -> float:
    return L + v * (W - L - R)


def y(v: float) -> float:
    return H - B - v * (H - T - B)


def main(out: Path) -> None:
    metrics = json.loads((HERE / "metrics.json").read_text())
    units = [u for u in json.loads((out / "units.json").read_text()) if u["split"] == "test"]
    scores = {p.stem: json.loads(p.read_text())["scores"][metrics["question"]]
              for p in (out / "runs/test/items").glob("*.json")}  # fmt: skip
    natural = [min(scores[s["item"]] for s in u["sentences"])
               for u in units for s in u["sentences"] if s["llm_flagged"]]  # fmt: skip
    points = sorted(metrics["curve"], key=lambda p: p["units_skipped"])
    for p in points:
        p["still_routed"] = sum(m <= p["t"] for m in natural) / len(natural)

    svg = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" '
           f'font-family="system-ui, sans-serif" font-size="12">',
           f'<rect width="{W}" height="{H}" fill="{SURFACE}"/>',
           f'<text x="{L}" y="24" font-size="14" font-weight="600" fill="{INK}">'
           'Held-out: share of verify units skipped vs. what still reaches the LLM</text>']  # fmt: skip
    for v in (0, 0.25, 0.5, 0.75, 1):
        svg += [f'<line x1="{L}" x2="{W - R}" y1="{y(v)}" y2="{y(v)}" stroke="{GRID}"/>',
                f'<text x="{L - 8}" y="{y(v) + 4}" text-anchor="end" fill="{MUTED}">{v:.0%}</text>',
                f'<text x="{x(v)}" y="{H - B + 18}" text-anchor="middle" fill="{MUTED}">{v:.0%}</text>']  # fmt: skip
    svg.append(f'<text x="{(L + W - R) / 2}" y="{H - 12}" text-anchor="middle" fill="{MUTED}">'
               "verify units skipped (Section and overview)</text>")  # fmt: skip
    llm = metrics["t_route"]["llm_alone_catch"]["value"]
    svg += [f'<line x1="{L}" x2="{W - R}" y1="{y(llm)}" y2="{y(llm)}" stroke="{MUTED}" stroke-width="1"/>',
            f'<text x="{W - R - 4}" y="{y(llm) - 6}" text-anchor="end" fill="{MUTED}">'
            f"LLM alone catches {llm:.0%}</text>"]  # fmt: skip
    for name, anchor, dx in (("t_route", "end", -4), ("t_route_alt", "start", 4)):
        v = metrics[name]["units_skipped"]["value"]
        svg += [f'<line x1="{x(v)}" x2="{x(v)}" y1="{T - 4}" y2="{H - B}" stroke="{MUTED}" stroke-width="1"/>',
                f'<text x="{x(v) + dx}" y="{T - 8}" text-anchor="{anchor}" fill="{MUTED}">'
                f"{name} ({v:.1%})</text>"]  # fmt: skip
    for key, label, color in SERIES:
        path = " ".join(f"{'M' if i == 0 else 'L'}{x(p['units_skipped']):.1f},{y(p[key]):.1f}"
                        for i, p in enumerate(points))  # fmt: skip
        svg.append(f'<path d="{path}" fill="none" stroke="{color}" stroke-width="2" '
                   'stroke-linejoin="round"/>')  # fmt: skip
    for n, (_, label, color) in enumerate(SERIES):  # legend in the right gutter
        ly = T + 40 + n * 22
        svg += [f'<line x1="{W - R + 16}" x2="{W - R + 32}" y1="{ly - 4}" y2="{ly - 4}" '
                f'stroke="{color}" stroke-width="2"/>',
                f'<text x="{W - R + 38}" y="{ly}" fill="{INK}">{label}</text>']  # fmt: skip
    svg.append("</svg>")
    (HERE / "curve.svg").write_text("\n".join(svg) + "\n")


if __name__ == "__main__":
    main(Path(sys.argv[1]).expanduser())
