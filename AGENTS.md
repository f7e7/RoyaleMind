# RoyaleMind Engineering Constraints

RoyaleMind is a read-only Clash Royale analysis and offline-simulation application. These constraints apply to all implementation work in this repository.

## Product and Safety Boundaries

- Acquire screenshots or frames for analysis only. Android integration may query device information and request screenshots; it must not send touch, key, swipe, or other gameplay input.
- Do not manipulate the game client, inspect protected game internals, bypass protections, or claim access to information not visible in supported observations.
- Keep the initial application local and offline. Do not add a server, database, cloud dependency, or language model without a concrete requirement and an explicit design update.
- Keep dashboard code out of capture, vision, state-estimation, strategy, and simulation logic.

## Data and Confidence

- Unknown values remain unknown; never substitute a convenient default for an unobserved value.
- Distinguish observed facts from inferred estimates in types and serialized data. An inference must not be promoted to an observation by state merging.
- Probabilistic observations and estimates include confidence or a probability distribution and provenance where applicable (source, timestamp, and method/model version).
- Preserve observation timestamps. State fusion must handle missing frames, out-of-order input, stale evidence, device disconnection, and low-confidence detections explicitly.
- Validate external and configuration data at boundaries. Invalid configuration and malformed frames fail safely with actionable diagnostics.

## Architecture and Dependencies

- Preserve the module boundaries described in `docs/architecture.md`: capture, vision, state, strategy, simulation, dashboard, configuration, and evaluation/testing.
- Strategy and simulation depend on domain data and explicit interfaces, never on OpenCV, NumPy image representations, ADB commands, or Streamlit.
- Vision recognizes visible evidence; it must not contain tactical rules. Strategy ranks options; it does not issue actions.
- Prefer small typed interfaces and independently testable components. Use Python 3.12 or a compatible supported version, Pydantic for validated boundary/domain models, pytest for tests, and structured logging.
- Use OpenCV and NumPy for image processing, ADB for optional Android screenshot capture, and Streamlit for the initial local dashboard. Add Ultralytics/YOLO only after collection, annotation, and baseline evaluation justify it.
- Do not introduce FastAPI, a database, distributed services, or an LLM without an approved concrete requirement.

## Testing, Data, and Documentation

- Separate unit tests, integration tests, and evaluation benchmarks. Keep deterministic tests independent of a connected phone and external model downloads.
- Use synthetic fixtures and intentionally recorded screenshots for repeatable vision/evaluation tests. Document provenance and acquisition conditions for recorded data.
- Do not fabricate model weights or report unimplemented/unevaluated capabilities as available.
- Keep secrets, personal data, generated frames, recordings, and model weights out of Git unless their inclusion is explicitly intended and reviewed.
- Document system dependencies, configuration, reproducible setup, limitations, and test commands as features are implemented.
- Before changing an existing file, inspect it and preserve unrelated user work. Do not claim tests pass unless they were run.

## Change Discipline

- Implement only the current approved phase in `docs/implementation-plan.md`; phase acceptance criteria are gates, not an instruction to implement later phases early.
- Update architecture and implementation documentation when a change alters boundaries, data semantics, supported behavior, or phase assumptions.
- Prefer the smallest independently verifiable change that satisfies the requirement.
