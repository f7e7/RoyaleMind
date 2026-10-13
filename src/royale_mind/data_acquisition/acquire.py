"""Bounded, retrying, idempotent JSON acquisition with SHA-256 manifests."""

from __future__ import annotations

import hashlib
import json
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import cast
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from pydantic import BaseModel, ConfigDict, Field

from royale_mind.data_acquisition.catalog import (
    CR_API_DATA_COMMIT_DATE,
    CR_API_DATA_REPOSITORY,
    CR_API_DATA_REVISION,
    LICENSE_STATUS,
    MAX_SOURCE_BYTES,
    MAX_TOTAL_BYTES,
    SOURCES,
)


class AcquisitionError(RuntimeError):
    """Source acquisition failed or violated a safety bound."""


class SourceFileManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    category: str
    url: str
    repository_revision: str
    repository_commit_date: str
    license: str | None = None
    license_status: str
    repository_reported_size_bytes: int
    retrieved_at: datetime
    downloaded_size_bytes: int
    sha256: str
    raw_path: str
    currentness: str = "unknown; pinned source last changed October 2023"


class AcquisitionManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: int = 1
    source_repository: str
    retrieved_at: datetime
    files: list[SourceFileManifest] = Field(default_factory=list)


def _download(url: str, timeout_seconds: float, retries: int, max_bytes: int) -> bytes:
    last_error: Exception | None = None
    for attempt in range(retries + 1):
        request = Request(url, headers={"User-Agent": "RoyaleMind-data-research/0.1"})
        try:
            with urlopen(request, timeout=timeout_seconds) as response:
                content_length = response.headers.get("Content-Length")
                if content_length is not None and int(content_length) > max_bytes:
                    raise AcquisitionError(
                        f"Source reports {content_length} bytes, exceeding {max_bytes}-byte limit"
                    )
                content = response.read(max_bytes + 1)
                if len(content) > max_bytes:
                    raise AcquisitionError(f"Downloaded content exceeds {max_bytes}-byte limit")
                return cast(bytes, content)
        except AcquisitionError:
            raise
        except (HTTPError, URLError, TimeoutError, OSError) as exc:
            last_error = exc
            if isinstance(exc, HTTPError) and exc.code not in {408, 429, 500, 502, 503, 504}:
                break
            if attempt < retries:
                time.sleep(min(0.5 * (2**attempt), 4.0))
    raise AcquisitionError(f"Could not retrieve {url}: {last_error}") from last_error


def acquire_catalog(
    output_root: Path,
    *,
    timeout_seconds: float = 20.0,
    retries: int = 2,
    accept_unknown_license_local_only: bool = False,
) -> AcquisitionManifest:
    """Acquire pinned source JSON; unknown-license import requires explicit local-only consent."""

    if not accept_unknown_license_local_only:
        raise AcquisitionError(
            "RoyaleAPI cr-api-data has no declared repository license. Re-run with "
            "accept_unknown_license_local_only=True for private research only; do not redistribute."
        )

    total_size = sum(source.repository_size_bytes for source in SOURCES)
    if total_size > MAX_TOTAL_BYTES:
        raise AcquisitionError(
            f"Catalog expected size {total_size} exceeds {MAX_TOTAL_BYTES}-byte total limit"
        )

    raw_root = output_root / "raw" / "card_metadata" / CR_API_DATA_REVISION
    manifest_path = output_root / "manifests" / "cr-api-data.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    if manifest_path.exists():
        try:
            existing = AcquisitionManifest.model_validate_json(manifest_path.read_bytes())
        except (OSError, ValueError) as exc:
            raise AcquisitionError(f"Existing manifest is invalid: {manifest_path}: {exc}") from exc
        expected = {source.name: source for source in SOURCES}
        if len(existing.files) != len(expected) or {item.name for item in existing.files} != set(
            expected
        ):
            raise AcquisitionError(
                f"Existing manifest is incomplete or unexpected: {manifest_path}"
            )
        for item in existing.files:
            source = expected[item.name]
            path = raw_root / source.relative_path.removeprefix("docs/json/")
            if item.repository_revision != CR_API_DATA_REVISION or item.url != source.url:
                raise AcquisitionError(
                    f"Existing manifest source differs from pinned catalog: {item.name}"
                )
            if Path(item.raw_path).resolve() != path.resolve():
                raise AcquisitionError(
                    f"Existing manifest path differs from pinned catalog: {item.name}"
                )
            try:
                content = path.read_bytes()
                json.loads(content)
            except (OSError, ValueError) as exc:
                raise AcquisitionError(f"Existing snapshot is unreadable: {path}: {exc}") from exc
            if (
                len(content) != item.downloaded_size_bytes
                or hashlib.sha256(content).hexdigest() != item.sha256
            ):
                raise AcquisitionError(f"Existing snapshot checksum or size mismatch: {path}")
        return existing
    files: list[SourceFileManifest] = []

    for source in SOURCES:
        content = _download(source.url, timeout_seconds, retries, MAX_SOURCE_BYTES)
        try:
            json.loads(content)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise AcquisitionError(f"Source {source.name} did not return valid JSON") from exc

        checksum = hashlib.sha256(content).hexdigest()
        raw_path = raw_root / source.relative_path.removeprefix("docs/json/")
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        if raw_path.exists():
            existing_checksum = hashlib.sha256(raw_path.read_bytes()).hexdigest()
            if existing_checksum != checksum:
                raise AcquisitionError(
                    "Refusing to overwrite existing source snapshot with a different checksum: "
                    f"{raw_path}"
                )
        else:
            temporary_path = raw_path.with_suffix(raw_path.suffix + ".tmp")
            temporary_path.write_bytes(content)
            temporary_path.replace(raw_path)

        files.append(
            SourceFileManifest(
                name=source.name,
                category=source.category,
                url=source.url,
                repository_revision=CR_API_DATA_REVISION,
                repository_commit_date=CR_API_DATA_COMMIT_DATE,
                license=None,
                license_status=LICENSE_STATUS,
                repository_reported_size_bytes=source.repository_size_bytes,
                retrieved_at=datetime.now(UTC),
                downloaded_size_bytes=len(content),
                sha256=checksum,
                raw_path=str(raw_path),
            )
        )

    manifest = AcquisitionManifest(
        source_repository=CR_API_DATA_REPOSITORY,
        retrieved_at=datetime.now(UTC),
        files=files,
    )
    temporary_manifest = manifest_path.with_suffix(".json.tmp")
    temporary_manifest.write_text(
        json.dumps(manifest.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary_manifest.replace(manifest_path)
    return manifest
