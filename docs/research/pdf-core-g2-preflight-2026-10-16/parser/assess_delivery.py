"""Separate rendered literal fidelity from exact raw Markdown preservation."""
from html.parser import HTMLParser
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
# These are authored synthetic source literals, not reconstructed model answers.
VISIBLE = {
    "ordinary-prose": "Normal task-specific prose, price $5, identifiers under_score_name and ReflACT, 3 < 4.",
    "escaped-literal-prose": "Literal __init__, _TEMP_, <widget>, price $5 and 3 < 4.",
    "unescaped-literal-prose": "Literal __init__, _TEMP_ and <widget>.",
    "inline-unknown-tag-code": "Use <widget> and a <= b literally.",
    "inline-html-code": "Use <b>bold</b> literally; keep under_score and a <= b.",
    "html-code-semantic": "Use <b>bold</b> literally.",
}


class VisibleText(HTMLParser):
    def __init__(self, source):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.feed(source)

    def handle_data(self, text):
        self.parts.append(text)

    def text(self):
        return "".join(self.parts).strip()


def main():
    results = json.loads((HERE / "run/results.json").read_text())
    assessed = []
    for case in results["controls"]:
        name = case["name"]
        raw_checks = case["representation_pass"]
        visible = {}
        representation = dict(raw_checks)
        for setting in raw_checks:
            if name in VISIBLE:
                rendered = (HERE / "run" / name / (setting + ".html")).read_text()
                visible[setting] = VisibleText(rendered).text()
                representation[setting] = visible[setting] == VISIBLE[name]
        assessed.append(dict(name=name, native_content_pass=case["content_pass"],
                             exact_markdown_pass=raw_checks, representation_pass=representation,
                             rendered_visible_text=visible,
                             evaluation="visible source literal" if visible else "registered exact Markdown/typed structure contract; no math renderer"))
    by_name = {c["name"]: c for c in assessed}
    assert by_name["unescaped-literal-prose"]["representation_pass"]["stock"]
    assert not by_name["unescaped-literal-prose"]["representation_pass"]["native-markdown"]
    assert by_name["escaped-literal-prose"]["representation_pass"]["native-markdown"]
    assert not by_name["escaped-literal-prose"]["representation_pass"]["stock"]
    assert not any(by_name["inline-html-code"]["representation_pass"].values())
    assert by_name["html-code-semantic"]["representation_pass"]["stock"]
    value = dict(
        scope="Supplemental assessment of already-registered source-fixed negative controls; raw parse/export artifacts unchanged. Visible-text assertions added after first run, not claimed as independent preregistered validation.",
        limitation="No general Markdown safety inference: intended literals, Markdown formatting and raw HTML require a provider format contract.",
        controls=assessed)
    destination = HERE / "delivery-assessment.json"
    assert not destination.exists(), "Assessment already saved"
    destination.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    print("Rendered negative controls verified; exact Markdown equality and visible delivery are recorded separately.")


if __name__ == "__main__":
    main()
