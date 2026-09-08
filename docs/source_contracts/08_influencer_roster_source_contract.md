# Source Contract 08 - Influencer Roster

## Source Identity

- Source ID: `SRC_INFLUENCER_ROSTER`
- Domain: Influencer / Creator Operations
- Source file: `influencer_data.csv`
- Source format: CSV export
- Target raw table: `raw.influencer_roster`
- Classification: Private business data

## Grain

One retained row represents one influencer roster export row.
Trailing blank spreadsheet-export rows are removed during extraction.

## Business Identity

`influencer_name` is the current roster identity field, but duplicate names are
allowed in raw data and must be evaluated downstream before entity matching.

## Verified Core Fields

- Influencer
- Follower
- Engangement Rate%
- BUDGET

All additional source fields are preserved in `source_payload` JSONB.
Raw text is preserved; numeric and percentage parsing belongs downstream.

## Data Quality and Drift

The current verified export contains 12 columns. Incompatible column-count drift
or a missing Influencer header must stop ingestion. Blank trailing export rows
are ignored, but blank influencer identities inside the retained data region are
not silently repaired. Duplicate influencer names are observable quality issues.

## Privacy Boundary

The private source may contain creator operational attributes or audience
segmentation fields. Payment, bank, address, phone, and contact sheets are not
part of this source contract. Private raw data must never be committed to Git,
published in CI artifacts, or used as portfolio demo data.

## Load Strategy

Snapshot ingestion with file-hash idempotency, file/run audit lineage, schema
validation, and raw-row identity by ingestion file plus source row number.

## Public Portfolio Policy

Tests and demonstrations must use synthetic schema-preserving creator data only.


## Runtime Data Quality Gate

Schema-critical headers are `Influencer`, `Follower`, `Engangement Rate%`, and
`BUDGET`. A missing core header or incompatible column count fails before load
and is recorded in `audit.schema_events`.

Row-level checks are recorded in `audit.data_quality_results`:

- blank influencer identity: `fail` and block raw load
- normalized duplicate influencer identity: `warning`, preserve raw rows
- follower not numeric/non-negative: `warning`
- budget not numeric/non-negative: `warning`
- engagement rate not parseable or outside 0..100: `warning`

Warnings never mutate, deduplicate, or discard raw source rows.

## Multi-Workbook Boundary

This contract applies only to the verified `influencer_data.csv` export. Private
client workbooks contain heterogeneous sheet layouts and must not be forced into
this contract. Each materially different workbook layout requires profiling and
a separately verified intake contract or adapter before ingestion.
