# Localized representation review addendum

The pre-implementation oracle requires preservation of exact symbols and localized
uncertainty. Comparing the independent historical source transcript with the new
helper's members found a further depth-limited discrepancy: native U+2212 (`−`)
versus extracted U+002D (`-`) in the recursive depth decrement. It also exists in
the immutable baseline assembly. The source rendering shows the decrement at this
location. No mathematical equivalence is established by the native transcript or
the parsed string.

`qualify.py` retains the complete whitespace-only comparison as **false** and emits
all difference ranges. The depth-limited expectation is exactly the two localized
differences (minus/hyphen and U+0007/absent in the body); iterative-deepening is
exactly U+0007/absent in the body. Both retain a separately source-linked U+0338.
Any other content difference or reordered surrounding body causes structural
qualification to fail. This is a source-review refinement of precise uncertainty,
not normalized symbol equality or production permission to accept arbitrary losses.

The output range offsets for these comparisons index whitespace-compacted source
and extracted sequences; member ranges separately index unchanged Docling text.
They must not be used interchangeably. Raw source and extraction bytes remain in
private artifacts, linked by hashes in evidence. The reviewed algorithm structure
is inspectable; symbol placement/meaning and final profile disposition remain a
separate acceptance decision. No source geometry is fabricated for the zero-width
combining mark; full-page source images are retained privately for inspection.

## Independent full captions (review correction)

Spec review proved that region membership plus figure number could accept corrupted
caption wording. `caption-oracle.json` now freezes full-caption whitespace-compacted
hashes from independent source text, plus the visually reviewed historical
uncorrected serialization. No expected caption text comes from the candidate.
PDFium native text boxes require the PDF crop origin offsets (21.6000,57.6000);
the first extraction omitted these offsets and returned unrelated text, so it was
rejected before freezing the caption oracle. Corrected extraction matches all four
visually reviewed captions.

The iterative caption has two native U+0002 line-end hyphen controls where historical
extraction joins `depthlimited`. Its native equality remains false, with this precise
uncertainty recorded; the full reviewed extracted serialization is separately hashed.
Other captions have whitespace-only native equality. This is not universal control-
character stripping. Corruption/truncation mutations retaining the figure number must
fail. The scorer concatenates caption members, allowing multiple-item representation.
