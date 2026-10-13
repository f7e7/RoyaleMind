# Arena Calibration

## Coordinate Convention

The calibration contract uses normalized screenshot coordinates `(x, y)` and normalized arena coordinates `(u, v)`, each in `[0, 1]`. Screenshot normalization is resolution independent: `x = pixel_x / image_width`, `y = pixel_y / image_height`. Arena normalized axes must be defined by a reviewed arena definition before interpreting them as tiles or deployable locations.

No exact gameplay-grid dimensions, bridge boundaries, river polygon, tower centers, or deployment zones are currently asserted. RoyaleAPI arena metadata and image repositories do not by themselves establish measured geometry.

## Recording Measurements

For each calibration, retain:

- Screenshot SHA-256, original width/height, supported device, orientation, aspect ratio, game mode, and observed UI/layout condition.
- Arena identifier only when visually verified; otherwise leave it unknown.
- At least three non-collinear landmark correspondences, each with a label, normalized screenshot point, normalized arena point, and measurement provenance (manual/verified method).
- Mapping method/version, fit RMSE, confidence, operator notes, and calibration timestamp.

Use landmarks with clear repeatable boundaries. Do not infer gameplay tile points from a stylized background, cropped screenshot, or tower appearance without independent validation. Repeat measurements across supported aspect ratios and layouts; do not reuse calibration when geometry/UI transforms differ without validation.

## Mapper

`royale_mind.data_acquisition.arena.fit_arena_mapper` fits a least-squares affine map from measured correspondences. The output calibration stores the fit RMSE and an explicitly uncalibrated confidence heuristic `exp(-RMSE / 0.02)`. This score is a fit diagnostic, not a statistically calibrated probability or gameplay accuracy measure. Degenerate/collinear inputs and mapped coordinates outside normalized arena space fail visibly.

Perspective/homography mapping, automatic arena detection, tower localization, deployment boundaries, and confidence calibration are not implemented. A screenshot-specific calibration belongs in an annotation/metadata record, not as a global constant.
