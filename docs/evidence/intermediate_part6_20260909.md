# PART 6 — Intermediate Transformation Evidence

Date: 2026-09-09

## Private read-only profiling

- Product rows: 12; distinct product IDs: 12
- SKU rows: 15; distinct SKU IDs: 15
- SKU → Product matched rows: 15; unmatched: 0
- Order rows: 5,249
- Order → SKU matched rows: 5,229; unmatched: 20
- Nonblank creator rows: 3,285
- Conservative creator → influencer matched rows: 210
- Private data writes during profiling: 0

## Overlap evidence

Shop Analytics contained 241 rows across 5 files and 136 distinct dates. 105 dates appeared more than once, proving that overlapping exports require deterministic current-date consolidation.
## PostgreSQL runtime reconciliation

Current local runtime produced zero row-count deltas for:

- current Products vs distinct staged product IDs
- current SKUs vs distinct staged SKU IDs
- current Order-SKU rows vs distinct staged business keys
- enriched Order-SKU rows vs current Order-SKU rows
- all four valid daily date grains

Unmatched SKU and creator references remained present with explicit match-status fields.

## Synthetic overlap validation

Two synthetic Shop observations for the same date resolved to one intermediate row. The later observation was selected, `source_observation_count` was 2, and cleanup left 0 synthetic raw rows.
## Synthetic current-state validation

Synthetic Product, SKU, and Order-SKU business keys each received two observations. Current models selected the later Product, SKU, and Order observation, reported two source observations, and enriched the Order-SKU to exactly one matched row.

Cleanup result:

- synthetic Order rows: 0
- synthetic SKU rows: 0
- synthetic Product rows: 0

## Validation status

Focused intermediate dbt tests: 57/57 PASS.
Final full-project validation is recorded at commit time.
## Final full gate

- `dbt compile`: PASS
- `dbt build`: 146/146 PASS
- Python compile: PASS
- Ruff: PASS
- pytest regression: 284 passed
- Airflow import errors: none
- PostgreSQL intermediate views: 11
- Final Product/SKU/Order/Enriched/Daily reconciliation deltas: 0
- PART 6 synthetic audit/raw residue after cleanup: 0
