# Dataset Collection and Ingestion

## Current Policy

The acquisition command retrieves only a fixed allowlist of pinned JSON metadata files from RoyaleAPI `cr-api-data`. It does not recursively download repositories, assets, model weights, videos, archives, or remote datasets. Each source is checked for HTTP status, timeout, maximum byte size, valid JSON, and SHA-256; transient HTTP/network failures are retried. Existing differing raw snapshots are never overwritten. Output is local under ignored `data/`.

The repository reports no license for `cr-api-data`. To acquire its small JSON files, the caller must use the explicit local-research acknowledgement. This is not legal permission to redistribute. Do not check these files into Git. Review source terms before moving them outside private research storage.

## Commands

```bash
royalemind acquire-data --accept-unknown-license-local-only --output data
royalemind audit-dataset /path/to/user-approved/dataset \
  --output data/reports/dataset-inspection.json
royalemind import-dataset-labels /path/to/user-approved/dataset \
  --output data/processed/visual_labels/annotations.json
royalemind export-data-schemas --output docs/schemas
```

`acquire-data` checks a complete existing manifest and all pinned raw files (source URLs, revision, paths, JSON syntax, byte lengths, and SHA-256) before reusing them without network access. If the manifest is missing, it retrieves the bounded allowlist. An incomplete manifest or changed snapshot fails closed; move it aside only after preserving and reviewing the local data. The command writes normalized card records and source-preserving arena/mode/timeline/evolution records, validation JSON, and coverage JSON. Exit status is nonzero on retrieval, checksum, schema, or card validation errors. Re-running it refreshes derived reports, while preserving the original manifest retrieval timestamps.

`audit-dataset` does not alter the supplied dataset; it writes only the requested inspection report. It inspects images (PNG/JPEG/WebP/BMP), Labelme JSON, and YOLO text labels. It reports unreadable images, unsupported file types, malformed/out-of-bounds annotations, exact duplicate image groups, and exact-hash duplicates appearing across named train/validation/test directories. It does not copy images or automatically canonicalize labels. `import-dataset-labels` writes normalized box records with source class IDs/names, image/annotation checksums, annotation format, split, and geometry; canonical class IDs remain `None` until an explicit reviewed mapping is supplied.

## Dataset Review Gate

Before importing a public visual dataset into any training or evaluation pipeline:

1. Pin a commit/release and record license, footage provenance, download size, expected disk use, image count, class map, image dimensions, annotation format, and apparent game version.
2. Review whether the declared license covers the underlying game/video imagery and commercial/non-commercial use; repository-code licensing alone may not.
3. Run `audit-dataset` on the user-approved local copy; inspect corruption, duplicates, labels, class counts, and unsupported files.
4. Check repeated frames and source-video/match overlap across splits. The current exact-byte audit is necessary but not sufficient; use match-level grouping and perceptual hashing before asserting held-out evaluation.
5. Store raw source data outside Git by default. Keep conversion outputs separate and preserve original class labels, label semantics, split metadata, source IDs, checksums, and transformations.
6. Only canonicalize classes after a reviewed mapping exists. Treat object crops, full-frame boxes, sprites, and rendered/generative composites as different tasks.

## Supported Annotation Checks

- Labelme JSON: shape labels and points are required; all supplied points must lie within the matching readable image. Polygon and rectangle point lists are structurally accepted, but semantic geometry is not otherwise transformed.
- YOLO normalized center/width/height lines: five-field standard rows are checked for numeric class IDs, positive dimensions, and boxes within `[0,1]`.
- The known KataCR-style extended row is supported only as twelve values: class ID, four normalized geometry values, affiliation (`0` or `1`), and six zero extension values. Other conventions are reported unsupported/malformed rather than guessed.
- Class IDs are counted as source IDs. No canonical Clash Royale class mapping is bundled because the candidate source maps are versioned and incompatible.

Unit tests synthesize small images and annotations. They verify tooling behavior only; they are not training/evaluation data and support no recognition-accuracy claim.
