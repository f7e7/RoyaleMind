# RoyaleMind Implementation Plan

## Planning Basis

The repository began with only `README.md`. Phase 0 establishes a Python package, dependency/tool configuration, validated domain contracts, local TOML settings, structured logging, ignore rules, tests, and setup documentation. Phase 1 adds deterministic file replay and a read-only ADB screenshot adapter. Vision and later analysis phases remain unimplemented. The plan is intentionally phased: do not start a later phase until the preceding acceptance criteria are met or the scope is explicitly revised.

The architecture and all phases preserve the read-only product boundary. No phase adds gameplay input automation, protected-client access, a web API, a database, distributed services, or an LLM.

## Phases and Acceptance Criteria

### Phase 0: Engineering Baseline and Domain Contracts

Status: implemented and verified with the documented install, test, lint, and formatting checks.

Establish package layout, supported Python version, dependency groups, local configuration conventions, logging, ignore rules, and core validated data contracts. Keep contracts minimal and align them with `docs/architecture.md`.

Acceptance criteria:

- A clean environment can install the documented core/test dependencies using documented commands.
- Package/import and lint/type-check policy (if adopted) is documented and reproducible.
- Editable installation provides a `royalemind` entry point for health and read-only device diagnostics; dependency and ADB errors are actionable.
- Linux/Debian prerequisites and application, test, lint, formatting, and type-check commands are documented.
- Domain contracts distinguish frame, observation, estimate, unknown, game state, capture status, and recommendation without representing an inference as a fact.
- Configuration validation rejects invalid values with actionable errors.
- Git ignore rules prevent accidental inclusion of local configuration/secrets, recordings/generated frames, caches, and model weights, while permitting intentional small synthetic fixtures.
- Unit tests cover model validation, unknown/inferred semantics, timestamps/provenance, and invalid configuration.
- Setup documentation identifies Python and optional ADB/system requirements; no model weights or dataset downloads are required.

### Phase 1: Deterministic Frame Sources and Read-Only Capture

Status: implemented and verified with replay and fake-runner capture/diagnostic tests. Live hardware was not required or tested.

Define a source protocol and implement replay from local image files plus an optional ADB screenshot adapter. Make replay the default development/test path. Do not implement continuous capture until the one-frame and lifecycle behavior is sound.

Acceptance criteria:

- Replay yields valid timestamped frame records and explicit errors/status for missing or unreadable files.
- Replay reads local PNG, JPEG, and WebP images; supplied timestamps are preserved, otherwise file modification time is used.
- ADB adapter supports device status and screenshot acquisition only; code inspection and tests establish that no touch/key/swipe/input command is issued.
- ADB supports optional device serial selection and configurable bounded timeout; absent ADB/device and malformed screenshot bytes map to typed failures.
- `royalemind health` reports required Python distributions and optional ADB executable availability; `royalemind devices` reports connected/authorized status using only `adb devices -l`.
- Timeout, no device, disconnect, malformed bytes, and unsupported image cases have typed/recoverable outcomes.
- Fake-source unit/integration tests cover failure and recovery behavior without a connected phone.
- System setup and data handling are documented; capture does not persist frames unless explicitly requested.

### Phase 2: Narrow Vision Baseline and Evaluation Harness

Choose a small, explicitly scoped set of visible interface elements after resolving device/layout assumptions. Implement preprocessing and a baseline detector/readout only for that scope. Establish labeled/annotated representative evaluation inputs before asserting accuracy. Do not introduce YOLO until data demonstrates a need.

Acceptance criteria:

- Vision accepts frame contracts and emits typed observations with class/value, timestamp, confidence, and method provenance.
- Unsupported resolution/layout, occlusion, unreadable value, and low-confidence paths produce unknown/uncertain results rather than fabricated values.
- Synthetic fixtures test mechanics; representative recorded fixtures are separately documented and have permission/provenance and a held-out split.
- Evaluation reports per-field measures appropriate to the task (including false positives and misses), limitations, and fixture conditions.
- No tactical recommendation logic is present in vision modules.

### Phase 3: Temporal State and Uncertainty Model

Fuse observations into state across frames, with explicit time/freshness and conflict handling. Add inferred opponent information only when its evidence and assumptions can be represented transparently.

Acceptance criteria:

- State distinguishes observed, inferred, stale, conflicting, and unknown data.
- Missing, duplicate, low-confidence, stale, and out-of-order observations have deterministic, documented behavior.
- Inference provenance/uncertainty is retained and cannot be serialized or rendered as an observation.
- Unit/property-style tests exercise state transitions and temporal edge cases using controlled clocks/inputs.
- Evaluation measures state stability and error under missed/noisy observations, not only per-frame vision accuracy.

### Phase 4: Tactical Ranking and Bounded Simulation

Implement a first narrow tactical ruleset and approximate scenario evaluator over domain state. Select mechanics and card metadata from reviewed, documented sources. Recommendations remain advisory and explain assumptions and uncertainty.

Acceptance criteria:

- Strategy and simulation import no capture, image-processing, device, or dashboard libraries.
- Inputs with unknown/uncertain state produce appropriately qualified rankings, including abstention or low-confidence outcomes where necessary.
- Each recommendation has rationale, assumptions, uncertainty/trade-off information, and a stable ranking contract.
- Simulation is deterministic for fixed inputs/seed and explicitly labels approximations; scenario regression tests cover hand-authored cases.
- Evaluation scenarios have expected qualitative/quantitative outcomes and document limits; no claim of exact game-engine fidelity is made.

### Phase 5: Local Streamlit Dashboard and End-to-End Workflow

Compose capture/replay, vision, state, strategy, and simulation through application orchestration and display status, evidence, uncertainty, and recommendations locally.

Acceptance criteria:

- Dashboard shows source/device status, current frame/state age, visible observations with confidence/provenance, inferred estimates distinctly, and unknown/stale/error states.
- Dashboard renders ranked advice and its explanation but has no action execution path or input controls.
- End-to-end replay works without ADB or network access and is deterministic for fixed fixtures/configuration.
- Integration tests cover source failure, empty/low-confidence observations, stale state, and normal replay.
- Manual verification instructions cover a supported desktop browser size and mobile/narrow layout if the dashboard is intended for phone browsers.
- Reproducible installation, run, testing, evaluation, privacy, and known limitations are documented.

### Phase 6: Evidence-Based Expansion (Optional)

Expand supported devices/elements, introduce a YOLO/Ultralytics detector, improve tracking, or optimize throughput only in response to measured gaps. This phase is not required to deliver the initial offline analysis workflow.

Acceptance criteria:

- The expansion addresses a documented evaluation or user requirement, with baseline results retained for comparison.
- Dataset/model provenance, rights, versioning, resource needs, and evaluation protocol are reviewed.
- Model artifacts are not fabricated, committed, or downloaded implicitly; an explicit acquisition/load workflow and failure behavior exist.
- Accuracy, latency, and resource changes are measured on representative held-out cases and documented before capability claims change.

## Initial Testing Strategy

- **Unit tests:** domain/Pydantic validation; configuration; confidence/provenance semantics; state transition and freshness policies; strategy ranking; deterministic simulation. Tests use fixed timestamps, clocks, inputs, and random seeds.
- **Integration tests:** fake frame source through preprocessing/vision adapters and state orchestration; ADB adapter command construction and failure mapping without relying on a live device; replay-to-recommendation path. Hardware tests may be optional and separately marked.
- **Evaluation benchmarks:** versioned, documented screenshots and annotations for each supported layout/element; held-out examples; per-field precision/recall or value error as appropriate; confidence calibration where feasible; state stability with missed/noisy frames; capture-to-state latency and memory on representative hardware. Keep benchmark results distinct from unit-test pass/fail.
- **Synthetic fixtures:** use for deterministic geometry, parsing, blank/occluded frames, invalid input, and regression mechanics. Synthetic images do not substantiate real-game recognition performance.
- **Data safety:** no secrets or personal screenshots in fixtures; document consent/provenance, sanitize identifiers, keep raw recordings and model weights out of Git by default, and make any intentional checked-in sample small and explicitly approved.
- **Continuous verification:** run formatting/static checks selected in Phase 0, unit tests for every change, integration tests for boundary changes, and relevant evaluation benchmarks before changing a capability or accuracy claim.

## Dependencies and Gates

- Start with Python, Pydantic, pytest, Ruff, and Pillow for the implemented package/capture boundaries. NumPy/OpenCV and Streamlit are deferred until their phases; keep ADB as an optional external executable and YOLO deferred.
- Pin supported dependency versions when packaging is added. Separate runtime, development/test, and optional live-capture/model dependencies to avoid requiring a phone or model for offline tests.
- User decisions listed in `docs/architecture.md` are phase-specific gates: device/layout decisions before Phase 1/2; scope and data policy before Phase 2; rule-data source before Phase 4; latency target before performance optimization. Reasonable local-only defaults may be documented for exploration but must not be presented as user-approved product requirements.
- Each phase should produce independently testable changes and update docs when it resolves or changes a decision. Do not add future-phase components speculatively.
