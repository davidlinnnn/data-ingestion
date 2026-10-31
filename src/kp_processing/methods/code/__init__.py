"""code: a code block reconstructed from the native text layer, with indentation recovered
from character x coordinates (#84 F14: native CER median 3.7%, all from spacing)."""

from typing import Any

from kp_processing.methods import MethodOutput

ID = "code"
VERSION = 1
ORIGIN = "reconstruction"


def run(item: dict[str, Any], inputs: list[bytes]) -> MethodOutput:
    """inputs = [source PDF]. Reads the characters of page item["page"] with PDFium whose box
    centre lies inside item["bbox"] (PDF points, BOTTOMLEFT origin as docling dumps it), groups
    them into lines and recovers indentation, after #84's extract_native.py and metrics.py
    native_char_lines (research commit 2524a1a5, pdf-core-w3b-2026-10-20/code-native-v4-utf16):

    - a character joins a line when the vertical centres differ by at most 0.3 x the smaller
      line height; lines run top to bottom, characters left to right;
    - unit = median width of positioned space characters; without any, for a monospaced font
      (MAD of letter and digit widths <= 3% of their median), the median gap between
      neighbouring character x positions within 0.7x..1.5x the median width;
    - indent columns = round((line x_left - min x_left of the block) / unit); a rounding error
      above 0.3 on any line makes signals["indent_quantized"] False (otherwise True);
      without a unit, 4 spaces per distinct x level and indent_quantized False;
    - positioned PDF spaces are kept; a gap wider than 0.65 x unit between two non-space
      characters inserts max(1, round(gap / unit)) spaces.

    success  content = lines joined with "\\n", each indented with spaces, no trailing newline
    failed   reason NO_TEXT_LAYER when no character lies inside the box; the VLM fallback for
             such blocks arrives with #133
    No files, no evidence."""
    raise NotImplementedError
