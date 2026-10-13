# RoyaleMind

RoyaleMind is a read-only Clash Royale analysis and offline-simulation project. The current code provides validated domain contracts, local configuration/logging, deterministic image replay, and optional read-only ADB screenshots. Vision, temporal state fusion, strategy, simulation, and dashboard workflows are not implemented yet.

## Linux and Debian Setup

Requirements: Python 3.12 or newer. On Debian/Ubuntu, install system prerequisites manually (application code never installs system packages):

```bash
sudo apt update
sudo apt install python3 python3-venv python3-pip adb
```

`adb` is optional if using frame replay only. Some distributions package Android Platform Tools as `android-sdk-platform-tools`; package names can vary. Alternatively, install Google's Android SDK Platform Tools and put its `platform-tools` directory on `PATH`. Connect the phone over USB and authorize this computer using the Android debugging prompt. RoyaleMind's diagnostics only inspect ADB device status; they do not change device settings.

Create an isolated Python environment and install RoyaleMind in editable mode with development tools:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[dev]'
```

This installs the `royalemind` executable and Python dependencies without changing system Python packages. Configuration is optional and local. Copy the following shape to an ignored `royalemind.toml` or point `ROYALEMIND_CONFIG` at another TOML file:

```toml
log_level = "INFO"
log_json = true
data_dir = "data"
adb_path = "adb"
adb_timeout_seconds = 10.0
# device_serial = "your-device-serial"
```

Run the app entry point and diagnostics:

```bash
royalemind --help
royalemind health
royalemind devices
```

To save one screenshot after manually connecting and authorizing a phone, first read
[the USB capture procedure](docs/android-capture.md). `capture-frame` uses only ADB status
and screenshot requests; it writes an ignored image and JSON metadata pair and never
replaces an existing pair:

```bash
royalemind devices
royalemind capture-frame --serial YOUR_DEVICE_SERIAL --output-dir data/captures
```

Running `royalemind` with no subcommand is equivalent to `royalemind health`. `health` requires installed Python dependencies and reports missing ADB as a warning, because replay remains available without a phone. `devices` exits non-zero when ADB is missing, no device is connected, or any listed device is unauthorized/offline. Use `--log-level DEBUG|INFO|WARNING|ERROR|CRITICAL` to override the configured level. Application analysis workflows are not implemented yet.

Run deterministic tests, linting, formatting, and type checking:

```bash
pytest
ruff check .
ruff format --check .
mypy
```

ADB and physical devices are not required for ordinary unit tests; device subprocess calls are mocked.

## Data Research Tools

The current data pipeline retrieves a bounded, pinned JSON metadata allowlist only. RoyaleAPI `cr-api-data` has no declared repository license, so its import requires an explicit private-research acknowledgement and stays in ignored local `data/`:

```bash
royalemind acquire-data --accept-unknown-license-local-only --output data
royalemind audit-dataset /path/to/approved/dataset --output data/reports/dataset-inspection.json
royalemind export-data-schemas --output docs/schemas
```

Review [data sources](docs/data-sources.md), [measured coverage and gaps](docs/data-coverage.md), [dataset ingestion policy](docs/dataset-collection.md), and [arena calibration](docs/arena-calibration.md) before importing third-party imagery or using source mechanics as current facts.

The configuration loader reads `royalemind.toml` (or the path in `ROYALEMIND_CONFIG`) when present. A missing file uses validated local defaults. Live capture is optional and requires Android Platform Tools (`adb`) installed and an authorized device; replay tests do not require ADB. Capture supports PNG, JPEG, and WebP screenshots and does not persist acquired frames. Keep private configuration, screenshots, recordings, datasets, and generated model artifacts out of Git.

Phase 1 exposes `ReplayFrameSource` and `AdbScreenshotSource` through `royale_mind`. They return a `Frame` containing encoded image bytes and validated `FrameMetadata`. The ADB source runs only `get-state` and `exec-out screencap -p`; it does not send gameplay input. Computer vision and tactical recommendations are not implemented.

See [the architecture](docs/architecture.md) and [implementation plan](docs/implementation-plan.md) for module contracts, phase gates, supported behavior, and limitations.
