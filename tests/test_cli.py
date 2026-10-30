import re

from kp_processing.cli import main
from kp_processing.profile import PROFILES_DIR


def test_profile_prints_every_method_identity(capsys):
    assert main(["profile"]) == 0

    lines = capsys.readouterr().out.splitlines()
    assert len(lines) == 7
    assert re.fullmatch(
        r"docling-parse@1  module_digest=[0-9a-f]{64}  components="
        r"docling-slim@2\.132\.0,layout-heron@8f39ad3c,tableformer-accurate@v1,rapidocr-ppocrv6-small",
        lines[0],
    )
    assert re.fullmatch(r"table-status@1  module_digest=[0-9a-f]{64}  components=", lines[5])


def test_profile_takes_a_path(capsys):
    assert main(["profile", str(PROFILES_DIR / "paper-pdf@1.yaml")]) == 0
    assert len(capsys.readouterr().out.splitlines()) == 7


def test_a_bad_profile_exits_1_with_the_reason_on_stderr(tmp_path, capsys):
    bad = tmp_path / "bad.yaml"
    bad.write_text((PROFILES_DIR / "paper-pdf@1.yaml").read_text().replace("code@1:", "code@9:"))

    assert main(["profile", str(bad)]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "code" in captured.err
