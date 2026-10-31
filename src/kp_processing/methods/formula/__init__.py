"""formula: LaTeX for a display formula read by the VLM from its region of the page image,
checked against the numbers and operators of the native text layer (#129, status rule v1)."""

from typing import Any

from kp_processing.methods import InventoryItem, MethodOutput

ID = "formula"
VERSION = 1
ORIGIN = "reconstruction"
TARGET = ("texts", "formula")
INPUTS = ("page_image", "source")


def request(item: InventoryItem, inputs: list[bytes]) -> dict[str, Any]:
    """Messages: a system prompt (untrusted source content; answer only in the schema; LaTeX of
    the formula alone, without its equation number) and one user message with the crop of the
    page image to item["bbox"] (scaled by the page image's pixels per PDF point, either
    coord_origin) as a PNG data URL, detail "high". response_format: the strict json_schema
    named ID for {"latex": string}."""
    raise NotImplementedError


def parse(item: InventoryItem, inputs: list[bytes], content: str) -> MethodOutput:
    """InvalidOutput("EMPTY_OUTPUT") when content or latex is blank; InvalidOutput(
    "SCHEMA_INVALID") when content is not JSON matching the schema. Otherwise outcome success,
    content = the latex string, files {"crop.png": the crop sent}, evidence ["crop.png"],
    signals {"native_text": the native text}, and contradictions ["FORMULA_NATIVE_MISMATCH"]
    when the native text has a digit or an operator and the two differ in either multiset:

      native text  the characters of page item["page"] of the source whose tight box centre
                   lies inside item["bbox"] (as code reads them), in reading order, with a
                   trailing equation number such as "(3)" or "(2.1a)" removed
      latex        with \\tag{...} removed; \\times \\div \\pm \\leq \\le \\geq \\ge \\neq \\ne
                   \\approx \\lt \\gt mapped to x-sign, division sign, plus-minus, <=, >=, !=,
                   approx, <, >; every other \\command name dropped
      both         NFKC-normalised; U+2212 and U+2013 read as "-"
      digits       multiset of 0-9; operators  multiset of + - = < > and the mapped signs
    """
    raise NotImplementedError
