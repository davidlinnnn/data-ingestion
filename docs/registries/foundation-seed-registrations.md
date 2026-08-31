# Foundation Seed Registrations

**Document status:** Governed registry seed data (Baseline §2, §12.1)
**Owner:** Foundation registry owner — per Baseline §12.1, every registration and every immutable schema version names an accountable owner

This document holds the initial Foundation-owned registry content referenced by
[ARCHITECTURE-BASELINE.md](../../ARCHITECTURE-BASELINE.md) §11.4, §12.2, and
§12.3. It is registry data, not frozen baseline text: every entry follows the
registry gates in Baseline §12, and a change that satisfies those gates does not
trigger architecture re-review (Baseline §24).

The five Standard Canonical Element Ancestors — `container`, `text`, `record`,
`field`, `media` — are the closed fallback vocabulary defined normatively in
Baseline §12.1 and are not modifiable here.

## 1. Initial Foundation Element Kinds

- **Document/layout:** document and section → `container`; heading, paragraph, caption → `text`; table and figure → `container`; row → `record`; cell → `field`.
- **Structured data:** dataset → `container`; column and value → `field`; record → `record`.
- **SaaS/API object graph:** collection → `container`; object → `record`; field → `field`.
- **Multimodal:** image, audio, video, and attachment → `media`.

Boundary rules for these kinds remain normative in Baseline §12.2: page and
spatial coordinates remain Source Evidence; foreign keys remain Canonical
Relationships; vendor concepts remain Owned Canonical Extensions; generated
transcripts and descriptions remain Enrichment Overlays.

## 2. Initial Foundation payload contracts

Initial payload contracts are logical and MAY omit optional values:

- `document`: optional source title, language, role;
- `document-section`: optional source role and identifier;
- `text-block`: required source-native text; optional language and source style;
- `table`: optional source role and identifier;
- `row`: optional source role;
- `cell`: required value; optional native type, row span, column span, header scope;
- `figure`: optional source role and identifier;
- `dataset`: required source-native name; optional dataset type;
- `column`: required name; optional native type, nullability, key role;
- `record`: optional source record type;
- `typed-value`: required value; optional field name and native type;
- `object-collection`: optional source object type;
- `object`: required source object type; optional source-native key;
- `media`: optional source role, filename, dimensions, duration, channels, source-native text alternative.

The content constraint remains normative in Baseline §12.3: these payloads
contain source-family facts only, and identity, provenance, location,
governance, and artifact metadata already present in common contracts are not
duplicated.

## 3. Initial Source Evidence locator families

- page region;
- text span;
- record key;
- record position (Revision-scoped; per Baseline §11.4 it never establishes stable identity);
- schema member or column;
- source-object reference;
- JSON Pointer;
- temporal range;
- artifact region.
