# RoyaleMind Architecture

## Status and Scope

This is the architecture proposal and current implementation baseline. Phase 0 foundations provide Pydantic domain contracts, local TOML settings, and standard-library structured logging. Phase 1 provides local replay and an optional read-only ADB screenshot source. Computer vision, temporal state fusion, tactical logic, simulation, and dashboard behavior remain unimplemented. No detection capability is implied.

RoyaleMind analyzes visible Clash Royale gameplay from a real Android phone and supports offline tactical analysis and simplified simulation. It is read-only: it must not send gameplay input or manipulate the game client. The initial deployment is a local Python application with a Streamlit dashboard, not a network service.

## Proposed Components

```text
Android device --(read-only screenshot request)--> capture --> Frame
                                                       |
Recorded frames ---------------------------------------+
                                                       v
                                                  vision --> Observations
                                                       |
                                                       v
                                         state estimation/fusion --> GameState
                                                                    |
                                             +-----------------------+-------------------+
                                             v                                           v
                                          strategy                                  simulation
                                             +-----------------------+-------------------+
                                                                     v
                                            application orchestration composes results
                                                                    |
                                                                    v
                                                        Streamlit dashboard
```

Configuration is loaded and validated at the application boundary. Structured logs provide diagnostics without becoming a source of game state. Tests and evaluation consume the same explicit input/output contracts but remain separate from runtime orchestration.

### `capture`

- Owns Android device status and acquisition of screenshots, plus an interchangeable local image replay source.
- `FrameSource.capture()` returns a `Frame` containing encoded image bytes and `FrameMetadata` (capture time, dimensions, source, freshness), or raises a typed `CaptureError`. The contract does not expose OpenCV/NumPy objects.
- ADB invocation is isolated here. Its allowed operations are limited to device status and screenshot acquisition; no input events or game-client manipulation.
- `ReplayFrameSource` accepts ordered image paths and optional explicit timestamps. Without timestamps it uses the file modification time; it never invents a current timestamp for a replayed frame. Replay metadata leaves freshness unknown because filesystem metadata alone does not establish currentness. It reports missing/invalid input and exhausted sequences explicitly.
- `AdbScreenshotSource` uses only ADB `get-state` and `exec-out screencap -p`. It supports optional serial selection and a bounded timeout. It handles missing devices, command failures, timeouts, absent bytes, and malformed/unsupported image data through typed errors; it does not persist frames.
- PNG, JPEG, and WebP are accepted after image validation. This only establishes that the payload is a readable image, not that it depicts a supported game screen.

### `diagnostics` and application entry point

- The `royalemind` console script enters through `royale_mind.cli:main`. With no subcommand it runs the startup health check; `health` checks required Python distributions and warns if optional ADB is missing; `devices` runs read-only `adb devices -l` and reports connected, unauthorized, offline, or absent devices.
- Device diagnostics never invoke ADB settings, pairing, restart, or input commands. Subprocess calls have bounded timeouts and actionable errors. Tests inject/mimic process results; ordinary tests require no phone.
- Startup, configuration, capture, diagnostics, and future analysis remain behind separate modules. `health` does not imply vision or dashboard readiness.

### `vision`

- Converts a frame into typed observations about visible UI/game entities and events. Early implementations may use documented image-processing heuristics; detector selection is an evaluated implementation decision.
- Receives image/frame abstractions and emits domain observations. It does not own tactical rules, temporal game-state decisions, or dashboard presentation.
- Each detection includes class/field, location or value, confidence, frame timestamp, and provenance (for example, method/version). Values that cannot be seen or read remain absent/unknown.
- OpenCV and NumPy are confined to image-processing implementation details. A YOLO/Ultralytics adapter is optional and must not be represented as available until data, weights, and evaluation exist.

### `state`

- Validates and fuses time-stamped observations into a temporally consistent `GameState`.
- Separates current observed values from inferred estimates, including opponent elixir and possible card-cycle hypotheses. Estimates carry confidence/distribution, provenance, and freshness; unknown remains a first-class value.
- Defines policy for conflicting, stale, low-confidence, missing, and out-of-order evidence. The policy is explicit and testable; a new frame does not automatically erase valid state, nor does old evidence silently become current.
- Provides domain types/contracts to strategy, simulation, and dashboard without exposing image arrays or device commands.

### `strategy`

- Ranks tactical alternatives (defense, offense, elixir efficiency, and counterattack opportunities) using only a `GameState` and explicit rules/configuration.
- Returns candidate recommendations with assumptions, rationale, expected trade-offs, and uncertainty. It never executes an action and must disclose when missing state prevents a reliable ranking.
- Has no direct dependency on ADB, OpenCV, NumPy, Streamlit, or a specific vision model.

### `simulation`

- Evaluates simplified, bounded future scenarios using domain state and simulation rules. It is not a claim of exact game-engine reproduction.
- Makes assumptions and uncertain inputs visible in outputs; scenarios must not convert hidden opponent information into facts.
- Is deterministic for a fixed input and seed where randomness is used, enabling repeatable tests and explanations.

### `dashboard`

- Streamlit is the initial local presentation and orchestration layer. It displays capture/device status, frame age, recognized state, observation provenance/confidence, uncertainty, and ranked recommendations.
- It calls application-facing interfaces and renders returned data. It does not implement vision algorithms, state fusion, or tactical logic.
- Must clearly distinguish observed and inferred values and show stale/unknown/error states rather than hiding them.

### `configuration`

- Loads local configuration and validates it with Pydantic. Configuration includes capture settings, image/layout calibration, confidence/freshness thresholds, and enabled analysis options as those are implemented.
- Invalid or unsupported values fail at startup or at the relevant boundary with actionable messages; no unsafe silent fallback is allowed.
- Secrets and private device/data details are not committed. The initial configuration format and location can be settled during the setup phase.

### `testing and evaluation`

- Unit tests cover deterministic domain logic and edge cases. Integration tests exercise boundaries using fake capture sources and controlled frame fixtures, without requiring a phone. Evaluation benchmarks measure vision/state performance on a versioned, documented dataset and are separate from ordinary unit-test pass/fail.
- Synthetic images support pipeline mechanics but cannot establish real-game recognition accuracy. Any accuracy claims require representative, held-out, documented evaluation data.
- Fixtures, recordings, weights, and generated output have explicit data-handling rules and are excluded from version control by default unless intentionally approved.

## Core Data Contracts

The current Pydantic contracts live in `src/royale_mind/domain.py` and are exported from `royale_mind`. They express:

- `FrameMetadata`: capture timestamp, positive dimensions, source, and freshness. Encoded bytes live in the capture `Frame` wrapper; pixel buffers belong to a future vision boundary, not the domain model.
- `ObservationMetadata` and `ObservationProvenance`: observation timestamp, confidence in `[0, 1]`, freshness, source, method, and method version.
- `CardObservation`, `UnitObservation`, `BuildingObservation`, `TowerObservation`, `ElixirObservation`, and `GamePhaseObservation`: frame-visible evidence. Unreadable or unavailable fields, including unknown team identity, are `None`; normalized `ImagePoint` and `BoundingBox` coordinates are validated in `[0, 1]`.
- `Estimate[T]`: an optional inferred value with confidence, timestamp, freshness, provenance, and assumptions. `GameState` keeps opponent elixir/card-cycle estimates in separate fields, never in observed elixir/card collections.
- `GameState`: optional state timestamp, frame and game-phase context, observed entity lists, and distinct optional estimates. Empty lists mean no observations are currently supplied, not evidence that no entities exist.
- `TacticalCandidateAction` and `TacticalRecommendation`: advisory domain values with action kind, rank, explanation, confidence, timestamps, assumptions, and trade-offs. They do not execute actions or implement strategy.

Pydantic is appropriate for validation at configuration and serialization boundaries. Internal immutable or otherwise controlled Python domain objects may be used where they simplify state transitions; implementation should avoid unnecessary duplicate representations.

The package exports these public model types from `royale_mind`. Models reject undeclared fields and are frozen against attribute reassignment. Lists use independent default factories. Their schemas are an initial stable contract and may be extended through reviewed changes; consumers should not infer freshness or certainty from omitted values.

## Dependency Map

```text
configuration --> capture, vision, state, strategy, simulation, dashboard
domain contracts --> vision, state, strategy, simulation, dashboard
capture -------> application orchestration -------> vision
vision --------> domain observation contracts ----> state
state ---------> strategy, simulation, dashboard
strategy ------> recommendation contract --+
simulation ----> scenario/result contract --+--> application orchestration --> dashboard
dashboard -----> application orchestration and presentation only
```

Dependency constraints:

- `strategy` and `simulation` depend only on domain contracts and configuration, not capture or pixel-processing libraries. The application orchestration layer may combine their independent outputs; avoid a dependency cycle between them.
- `vision` depends on frame contracts and image libraries, not strategy.
- `state` consumes observations, not frames or Android APIs.
- `dashboard` depends inward on application/domain interfaces; core modules never import Streamlit.
- `domain.py` has no OpenCV, NumPy, Ultralytics, ADB, or Streamlit dependency. `config.py` validates local TOML settings and `logging_setup.py` configures standard-library logging.
- Tests can substitute fake frame sources, vision implementations, clocks, and deterministic scenario inputs at boundaries.

## Suggested Technology and Dependency Policy

- Runtime baseline: Python 3.12 or a compatible supported Python version, pinned and documented once project packaging is introduced.
- Core: Pydantic for validated models/configuration; structured logging via the standard logging ecosystem or a selected structured formatter.
- Capture currently uses Pillow only to validate encoded PNG/JPEG/WebP bytes and read dimensions. NumPy and OpenCV remain deferred to vision. ADB is an external system executable, not a Python requirement; live capture reports its absence clearly.
- Dashboard: Streamlit, isolated from core domain logic.
- Testing: pytest; add coverage/property-based tools only when they address a concrete testing need.
- Optional model path: Ultralytics only after a baseline detector, labeled data, licensing/provenance review, and measurable evaluation criteria. Model weights are user-supplied or intentionally managed artifacts, never fabricated or silently downloaded.
- Avoid FastAPI, a database, distributed infrastructure, and LLM dependencies unless a specific product requirement changes the architecture and is reviewed.

## Current Package and Configuration

- Install the package and development tools in a virtual environment with `python -m pip install -e '.[dev]'`; Linux/Debian prerequisites and commands are documented in the repository README.
- `Settings` in `royale_mind.config` supports `log_level`, `log_json`, `data_dir`, `adb_path`, `adb_timeout_seconds`, and optional `device_serial`. It reads TOML from `royalemind.toml`, or from the path named by `ROYALEMIND_CONFIG`; callers may also provide an explicit path. Missing files use validated defaults; malformed TOML, invalid values, and unknown keys fail with `SettingsError` or Pydantic validation errors.
- `configure_logging` in `royale_mind.logging_setup` configures console output with JSON by default, or human-readable output when requested. Structured records should not include secrets, personal identifiers, or screenshot contents.
- `royalemind` is the installed command. Its `health` and `devices` subcommands are diagnostic-only; omitted command defaults to health. `--log-level` overrides the validated settings level.
- `royalemind health` checks required Python distributions; missing ADB is a warning because replay does not need it. The `devices` command treats no devices, unauthorized/offline devices, timeout, or command errors as a non-zero diagnostic result.
- Pillow is used by the capture boundary to validate and read image dimensions; NumPy, OpenCV, ADB Python wrappers, Streamlit, and model dependencies are not part of the core package. Android Platform Tools are an optional external prerequisite for live screenshots.

## Failure and Uncertainty Handling

- A disconnected device or absent frame changes capture status; it does not create a synthetic frame or imply that the last frame is current.
- Downstream state carries the age of its evidence. A configurable freshness policy can mark evidence stale, while preserving its history for analysis.
- Low-confidence detections may be retained as uncertain evidence or rejected according to documented thresholds; they are never silently upgraded to facts.
- Unknown opponent resources/card cycle remain unknown or distributional hypotheses. Tactical consumers must account for uncertainty and expose assumptions.
- Invalid configuration and malformed model output are boundary errors with diagnostic context and safe UI representation; they must not crash a long-running dashboard without an informative status.

## Security, Privacy, and Data Handling

- Device capture is read-only and local by default. No credentials or screenshots are transmitted to a remote service by this design.
- Screenshots may contain identifiers or personal information. Store recordings only when explicitly configured, document retention/location, and keep raw/generated frames and weights out of Git by default.
- Do not include secrets, private recordings, or user identifiers in logs. Logs should report operation, timing, status, and sanitized error details.
- Review licensing and terms for any collected gameplay imagery, card art, annotations, or external model before redistribution.

## Technical Risks and Mitigations

- **Resolution, orientation, scaling, and UI changes:** begin with explicit supported-device calibration and fixture metadata; detect unsupported geometry and fail visibly; test multiple resolutions before generalizing.
- **Visual ambiguity and animation/occlusion:** attach confidence and frame provenance, use temporal evidence conservatively, expose unknowns, and evaluate false positives as well as recall.
- **State drift from missed observations:** make freshness and conflict policy explicit, test missing/out-of-order frames, and avoid treating a single missed frame as a confirmed entity removal.
- **Limited labeled data/model overclaim:** start with a narrow, measured baseline; define annotation schema and held-out evaluation before training; do not claim general recognition from synthetic fixtures.
- **Opponent hidden information:** use estimates/distributions with assumptions and uncertainty, never display inferred values as observed facts, and test consumers against broad uncertainty.
- **Latency and resource use on a local machine:** measure capture-to-state latency and memory on representative hardware; use bounded frame queues and configurable sampling only if measured needs require them.
- **ADB availability and device variance:** isolate the adapter, document setup/permissions, make replay a first-class source, and test disconnect/reconnect paths without hardware.
- **Sensitive recordings and third-party assets:** default to no persistent recording, document data paths and retention, ignore generated artifacts, and review asset/model provenance.
- **Simplified simulation mismatch:** label simulation as approximate, make mechanics assumptions versioned/configurable, and compare only against documented scenarios rather than claiming engine fidelity.

## Open Decisions

These questions do not block documenting the architecture, but should be answered before the related implementation phase:

- Which Android versions, device models, screen resolutions, orientation, and display scaling must the first capture/vision slice support?
- Is live analysis required for the first usable milestone, or is replay of user-provided/recorded screenshots an acceptable initial workflow?
- What match modes and visible game elements are in the first recognition scope (for example, elixir/hand/towers only versus troops, buildings, and events)?
- May users persist screenshots locally for replay/evaluation? If yes, what default storage location and retention policy are acceptable?
- What machine/OS should setup documentation target, and should ADB be a required system prerequisite or an optional live-capture extra?
- What latency target is useful for the first live dashboard, and what resource constraints apply to the analysis machine?
- Which Clash Royale rules/card metadata source and licensing constraints should govern strategy/simulation data?
