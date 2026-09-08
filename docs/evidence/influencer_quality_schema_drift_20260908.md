# Influencer Quality and Schema Drift Evidence - 2026-09-08

## Privacy Scope

Analysis used private business files locally. This evidence contains only
anonymized structural statistics. No client names, creator identities, private
paths, payment details, or row values are included.

## Verified Roster Profile

- retained rows: 92
- source columns: 12
- blank influencer identities: 0
- normalized unique identities: 88
- duplicate normalized identity keys: 4
- rows participating in duplicate identities: 8
- invalid follower numeric/non-negative rows: 0
- invalid budget numeric/non-negative rows: 0
- engagement-format warning rows: 2

The verified file is therefore loadable with warnings, not silently cleaned.

## Multi-Workbook Structural Survey

A metadata-only survey covered 3 private workbooks and 9 influencer-oriented
sheets. Detected header positions varied from row 2 through row 13, and detected
header widths varied from 5 through 13 populated fields.

Shared structural fields across all 9 surveyed sheets were influencer identity,
TikTok reference, and follower count. Budget appeared in 6 of 9 sheets and an
explicit engagement-rate field appeared in 2 of 9 sheets.

Conclusion: these workbook layouts are not one stable physical source. They must
remain outside the verified roster contract until a layout-specific intake
profile is approved.

## Synthetic Runtime Validation

Three portfolio-safe runtime scenarios were executed through Airflow and
PostgreSQL:

1. duplicate identity plus malformed engagement -> warnings persisted, 2 rows
   loaded, file/run succeeded
2. blank identity with otherwise populated row -> DQ fail persisted, 0 rows
   loaded, file/run failed
3. column-count drift plus missing identity header -> schema events persisted,
   no DQ execution, 0 rows loaded, file/run failed

This validates the boundary order: schema -> data quality -> raw load.
