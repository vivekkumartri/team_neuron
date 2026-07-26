"""Schema -> fact -> passage memory-graph layer, adapted from MemGraphRAG.

See docs/adr/0001-memgraphrag-adaptation.md for why this is a from-scratch
reimplementation against this repo's own `ModelProvider`/Lakebase Postgres
rather than a vendored dependency on the upstream repo.
"""
