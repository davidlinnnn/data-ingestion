"""Enrichment Method packages. Each declares ID and VERSION; everything that shapes a
method's output (code, prompts, schemas, constants) lives inside its package, because
the package's source digest enters the reuse key (ADR-0010). The package name is the
method ID with dashes as underscores."""
