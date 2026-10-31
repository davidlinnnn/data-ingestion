import hashlib
import shutil
from pathlib import Path
from typing import Any

import pytest

from kp_processing.identity import canonical_json, module_digest, reuse_key
from kp_processing.profile import PROFILES_DIR, load_profile


def test_canonical_json_preserves_compact_sorted_json_bytes():
    assert canonical_json({"z": [None, True, 1.5, {"b": 2, "a": 1}], "a": "é"}) == (
        b'{"a":"\\u00e9","z":[null,true,1.5,{"a":1,"b":2}]}'
    )


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_canonical_json_rejects_nonfinite_numbers(value):
    with pytest.raises(ValueError):
        canonical_json({"value": value})


@pytest.fixture
def package(tmp_path: Path) -> Path:
    pkg = tmp_path / "site-a" / "formula"
    (pkg / "prompts").mkdir(parents=True)
    (pkg / "__init__.py").write_text('ID = "formula"\nVERSION = 1\n')
    (pkg / "prompts" / "system.txt").write_text("Transcribe the formula as LaTeX.\n")
    (pkg / "schema.json").write_text('{"type": "object"}\n')
    return pkg


@pytest.mark.parametrize("rel", ["__init__.py", "prompts/system.txt", "schema.json"])
def test_one_character_in_any_file_changes_the_digest(package, rel):
    before = module_digest(package)
    target = package / rel
    target.write_text(target.read_text().replace("o", "0", 1))

    assert module_digest(package) != before


def test_reinstalling_elsewhere_with_bytecode_keeps_the_digest(package, tmp_path):
    reinstalled = tmp_path / "site-b" / "formula"
    shutil.copytree(package, reinstalled)
    (reinstalled / "__pycache__").mkdir()
    (reinstalled / "__pycache__" / "__init__.cpython-312.pyc").write_bytes(b"\x00bytecode")
    (reinstalled / "prompts" / "stale.pyo").write_bytes(b"\x00")
    (reinstalled / ".DS_Store").write_bytes(b"\x00")
    (reinstalled / "prompts" / ".system.txt.swp").write_bytes(b"\x00")

    assert module_digest(reinstalled) == module_digest(package)


def test_renaming_a_file_changes_the_digest(package):
    before = module_digest(package)
    (package / "schema.json").rename(package / "schema2.json")

    assert module_digest(package) != before


def test_adding_an_empty_file_changes_the_digest(package):
    before = module_digest(package)
    (package / "empty.txt").write_text("")

    assert module_digest(package) != before


KEY_PARTS: dict[str, Any] = dict(
    document_uid="doc_7f3",
    method_ref="formula@1",
    components=["company-vlm/Qwen3.8-27B"],
    module_digest="ab12",
    input_digests=["d1", "d2"],
)


def test_reuse_key_is_sha256_of_the_compact_json_array():
    expected = hashlib.sha256(
        b'["doc_7f3","formula@1",["company-vlm/Qwen3.8-27B"],"ab12",["d1","d2"]]'
    ).hexdigest()

    assert reuse_key(**KEY_PARTS) == expected


@pytest.mark.parametrize(
    "part,value",
    [
        ("document_uid", "doc_other"),
        ("method_ref", "formula@2"),
        ("components", ["company-vlm/Qwen3.9-27B"]),
        ("module_digest", "ab13"),
        ("input_digests", ["d2", "d1"]),
    ],
)
def test_every_part_changes_the_key(part, value):
    assert reuse_key(**{**KEY_PARTS, part: value}) != reuse_key(**KEY_PARTS)


def test_no_ambiguity_between_parts():
    a = reuse_key(**{**KEY_PARTS, "components": ["a", "b"], "input_digests": []})
    b = reuse_key(**{**KEY_PARTS, "components": ["a"], "input_digests": ["b"]})

    assert a != b


def test_runtime_values_never_change_any_key(tmp_path):
    original = PROFILES_DIR / "paper-pdf@1.yaml"
    changed = tmp_path / "paper-pdf@1.yaml"
    text = original.read_text()
    changed.write_text(
        text.replace("vlm_concurrency_per_document: 4", "vlm_concurrency_per_document: 8")
        .replace("max_attempts: 3", "max_attempts: 5")
        .replace("summary_request_deadline_s: 120", "summary_request_deadline_s: 300")
    )

    def keys(path: Path) -> list[str]:
        p = load_profile(path)
        assert p.runtime  # the runtime section did load
        return [
            reuse_key("doc_1", m.ref, m.components, m.module_digest, ["in"])
            for m in p.methods.values()
        ]

    assert load_profile(changed).runtime != load_profile(original).runtime
    assert keys(changed) == keys(original)
