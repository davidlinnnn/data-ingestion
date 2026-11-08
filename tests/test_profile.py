from pathlib import Path

import pytest

from kp_canonicalization.identity import module_digest
from kp_canonicalization.methods import document_summary
from kp_canonicalization.profile import PROFILES_DIR, ProfileError, load_profile

PAPER_PDF_1 = PROFILES_DIR / "paper-pdf@1.yaml"
METHODS_DIR = Path(__file__).parents[1] / "src/kp_canonicalization/methods"


def variant(tmp_path: Path, old: str, new: str) -> Path:
    text = PAPER_PDF_1.read_text()
    assert old in text
    path = tmp_path / "variant.yaml"
    path.write_text(text.replace(old, new))
    return path


def test_paper_pdf_1_lists_its_eight_methods_with_declared_components():
    p = load_profile(PAPER_PDF_1)

    assert p.id == "paper-pdf@1"
    assert p.status_rule == "v1"
    assert [m.ref for m in p.methods.values()] == [
        "docling-parse@1",
        "picture-ocr@1",
        "picture-interpretation@1",
        "formula@1",
        "code@1",
        "table-status@1",
        "document-summary@2",
        "d3-check@1",
    ]
    assert p.methods["docling-parse"].components == (
        "docling-slim@2.132.0",
        "layout-heron@8f39ad3c",
        "tableformer-accurate@v1",
        "rapidocr-ppocrv6-small",
    )
    assert p.methods["table-status"].components == ()
    assert [lim.code for lim in p.limitations] == [
        "READING_ORDER_DEFECTS",
        "CAPTION_INTERRUPTS_BODY",
        "INLINE_MATH_NOT_RECONSTRUCTED",
        "INLINE_CODE_NOT_RECONSTRUCTED",
    ]
    assert p.runtime["vlm_concurrency_per_document"] == 4


def test_paper_pdf_1_sends_only_to_its_three_declared_services():
    # The inference egresses of the data-security design §5: the company VLM, the summary model
    # and the d3 decision model.
    p = load_profile(PAPER_PDF_1)

    external = {m.id: (m.service, m.components) for m in p.methods.values() if m.service}

    assert external == {
        "picture-interpretation": ("vlm", ("company-vlm/Qwen3.8-27B",)),
        "formula": ("vlm", ("company-vlm/Qwen3.8-27B",)),
        "code": ("vlm", ("company-vlm/Qwen3.8-27B",)),
        "document-summary": ("summary", ("company-vlm/Qwen3.8-27B",)),
        "d3-check": ("d3", ("company-d3/vllm-sr/d3-mini@bd0090dd",)),
    }


def test_a_method_calling_an_undeclared_service_refuses_to_load(monkeypatch):
    monkeypatch.setattr(document_summary, "SERVICE", "web-search")

    with pytest.raises(ProfileError, match="undeclared service 'web-search'"):
        load_profile(PAPER_PDF_1)


def test_each_method_carries_the_digest_of_its_own_package():
    p = load_profile(PAPER_PDF_1)

    assert p.methods["formula"].module_digest == module_digest(METHODS_DIR / "formula")
    assert p.methods["formula"].module_digest != p.methods["code"].module_digest


def test_a_version_the_package_does_not_declare_refuses_to_load(tmp_path):
    with pytest.raises(ProfileError, match="formula"):
        load_profile(variant(tmp_path, "formula@1:", "formula@2:"))


def test_a_method_without_a_package_refuses_to_load(tmp_path):
    with pytest.raises(ProfileError, match="document-category"):
        load_profile(variant(tmp_path, "table-status@1:", "document-category@1:"))


def test_a_quality_check_lacking_a_listed_methods_version_refuses_to_load(tmp_path, monkeypatch):
    monkeypatch.setattr("kp_canonicalization.methods.formula.VERSION", 2)
    with pytest.raises(ProfileError, match="d3-check@1 has no check for formula@2"):
        load_profile(variant(tmp_path, "formula@1:", "formula@2:"))


def test_a_malformed_method_key_refuses_to_load(tmp_path):
    with pytest.raises(ProfileError, match="expected <id>@<int>"):
        load_profile(variant(tmp_path, "formula@1:", "formula:"))


def test_a_missing_required_section_refuses_to_load(tmp_path):
    with pytest.raises(ProfileError, match="runtime"):
        load_profile(variant(tmp_path, "\nruntime:", "\nruntime_renamed:"))


def test_a_missing_runtime_key_that_the_code_reads_refuses_to_load(tmp_path):
    with pytest.raises(ProfileError, match="heartbeat_timeout_s.inference"):
        load_profile(variant(tmp_path, "{inference: 60, vlm: 90", "{vlm: 90"))


def test_a_runtime_key_that_is_not_a_number_refuses_to_load(tmp_path):
    with pytest.raises(ProfileError, match="start_to_close_s.inference is not a number"):
        load_profile(variant(tmp_path, "inference: 900}", 'inference: "900"}'))
