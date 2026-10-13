# Data Coverage Report

Acquisition/review date: **2026-10-13**. Machine-readable outputs are local and ignored by Git:

- Source manifest: `data/manifests/cr-api-data.json`
- Normalized records: `data/processed/cards/cards.json`
- Validation report: `data/reports/validation.json`
- Coverage report: `data/reports/coverage.json`
- Provenance-wrapped arena/mode/timeline source rows: `data/processed/arena_geometry/arena-source-records.json`, `data/processed/game_modes/`, and `data/processed/mechanics/evolution-mechanics.json`

## Measured Results

- Retrieved **16 pinned JSON files** from RoyaleAPI `cr-api-data` commit `d5461b0a59bff33c4da2fc845b07275b66b2d6ff`. All are in `data/raw/card_metadata/<revision>/`.
- Total raw JSON size is **9,964,371 bytes** (about 9.5 MiB); all 16 manifest lengths and SHA-256 checksums were rechecked against the local files. Total `data/` footprint including normalized records and reports is about **13 MB** in this environment.
- Normalization produced **128 distinct source-key records**, including 120 base records and 8 evolution variants, with **120 unique stable IDs**. This is a source-specific count, not a claim that 120 are current playable cards. Base/evolution rows share stable IDs intentionally.
- Validation report is valid with no duplicate keys, invalid elixir values, negative known nonnegative stats, or conflicting IDs outside recognized base/evolution variants. Signed source offsets/modifiers are retained and not falsely rejected as negative health/damage.
- Card coverage by field and source statistics is in `data/reports/coverage.json`. These values measure whether source fields are present, not whether they are current or gameplay-verified.
- No images, card art, arena backgrounds, trained weights, gameplay recordings, or user screenshots were acquired.
- No dataset was locally inspected; dataset reports remain empty. The data auditor is implemented and accepts a user-provided root.
- No labels were ingested because no user-approved local dataset was supplied. `import-dataset-labels` preserves original class IDs/names without an implicit canonical mapping.
- The provenance-wrapped source tables contain 79 arena metadata rows, 380 game-mode rows, 17 battle timelines, 320 spell-set rows, and 62 character-buff rows. These are historical source rows, not validated current rules.
- Geometry remains unmeasured. The schema and least-squares affine mapper require measured screenshot-to-arena correspondences and carry per-calibration confidence/RMSE; no map points have been supplied.

## Known Gaps

- Source is from October 2023. Current-game freshness and balance validity are unknown.
- `cr-api-data` has no declared repository license. Local import was explicitly acknowledged for private research only; do not publish raw or normalized records until terms/permission are resolved.
- Official API details require authenticated documentation and a user-managed token.
- Card-level field semantics and source statistic encodings need a schema-specific review; raw source fields are retained, not silently flattened into canonical game-mechanic claims.
- No complete verified catalog of current cards/evolutions, current balance stats, level-scaling formula, matchups, interactions, tower placement, bridge/river coordinates, or mode coverage is established.
- No visual assets or CV annotations are locally imported. Public datasets have stale versions, mixed conventions, questionable derived-footage rights, incomplete documentation, or leakage risks.
- The validator currently detects exact duplicate image bytes, not perceptual duplicates. Match/video-level split leakage beyond exact hashes remains unmeasured.
- Dataset auditor supports common Labelme and YOLO formats, but KataCR extended labels require compatible class-map/version review and are not silently canonicalized.

Coverage is not reported as a single percentage: the source does not define a complete current-game universe, and many requested mechanics are absent or unverified.

## Acquisition Task Status

- **Repository and architecture inspection — complete and verified.** Existing Phase 0/1 boundaries and working-tree changes were reviewed; data tooling remains separate from runtime vision and strategy.
- **Source discovery, revisions, licenses, and access — partially complete.** Candidate official and community sources, pinned revisions where available, rights questions, and access limits are documented. Authenticated official API details remain unavailable.
- **Card metadata and normalization — partially complete.** The 2023 pinned snapshot, unique keys, IDs, fields, and provenance validate locally. Current-game completeness and stat semantics are unverified.
- **Visual assets and CV dataset acquisition — blocked by licensing and missing approved input.** Zero images and annotations are local; public candidate datasets are documented but have unresolved footage/asset rights and version/split concerns.
- **Arena geometry and calibration — blocked by missing measured screenshots.** Historical arena metadata and a calibration contract exist; zero measured coordinate maps exist.
- **Game-mode rules and strategic references — partially complete.** Historical source rows are preserved with provenance; they have not been checked against current gameplay or converted into tactical rules.
- **Manifests, schemas, ingestion, and provenance — complete and verified for the scoped historical JSON import.** Visual labels remain unpopulated until a reviewed dataset is supplied.
- **Validation, tests, and coverage reports — complete and verified for the scoped local import.** Structural and field-presence checks do not establish game accuracy or vision performance.
- **Documentation and reproducible commands — complete and verified for the scoped local pipeline.** External data gates and Phase 2 fixture requirements remain open.

## Local Card-Field Counts

These counts are generated from retained source fields in `data/reports/coverage.json`; a populated field is not evidence that its value is current or experimentally confirmed. Current report covers 128 normalized card/evolution source-key records. Refer to that JSON for the full field-by-field count.
