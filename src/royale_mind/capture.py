"""Read-only screenshot acquisition and deterministic local frame replay."""

from __future__ import annotations

import subprocess
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path
from typing import Protocol

from PIL import Image, UnidentifiedImageError

from royale_mind.domain import FrameMetadata, Freshness


@dataclass(frozen=True, slots=True)
class Frame:
    """Validated encoded image bytes paired with image-library-free metadata."""

    metadata: FrameMetadata
    image_bytes: bytes
    image_format: str


class FrameSource(Protocol):
    """One-frame source interface implemented by replay and live capture."""

    def capture(self) -> Frame:
        """Acquire one frame or raise a typed `CaptureError`."""


class CaptureError(RuntimeError):
    """Base class for recoverable frame acquisition failures."""


class DeviceUnavailable(CaptureError):
    """ADB or a usable Android device is unavailable."""


class CaptureTimeout(CaptureError):
    """The device status or screenshot request exceeded its timeout."""


class InvalidFrame(CaptureError):
    """A frame is missing, unreadable, or not a supported image."""


Runner = Callable[..., subprocess.CompletedProcess[bytes]]
Clock = Callable[[], datetime]


def _validated_frame(
    image_bytes: bytes,
    captured_at: datetime,
    source: str,
    freshness: Freshness = Freshness.UNKNOWN,
) -> Frame:
    if not image_bytes:
        raise InvalidFrame("Screenshot source returned no image bytes")
    if captured_at.tzinfo is None or captured_at.utcoffset() is None:
        raise InvalidFrame("Frame timestamp must include timezone information")

    try:
        with Image.open(BytesIO(image_bytes)) as image:
            image.verify()
        with Image.open(BytesIO(image_bytes)) as image:
            image_format = image.format
            width, height = image.size
    except (Image.DecompressionBombError, UnidentifiedImageError, OSError, ValueError) as exc:
        raise InvalidFrame(f"Screenshot is not a valid supported image: {exc}") from exc

    if image_format not in {"PNG", "JPEG", "WEBP"}:
        raise InvalidFrame(f"Unsupported screenshot image format: {image_format}")

    return Frame(
        metadata=FrameMetadata(
            captured_at=captured_at,
            width=width,
            height=height,
            source=source,
            freshness=freshness,
        ),
        image_bytes=image_bytes,
        image_format=image_format,
    )


class ReplayFrameSource:
    """Read a configured image sequence without depending on an Android device."""

    def __init__(
        self,
        paths: Sequence[Path],
        timestamps: Sequence[datetime] | None = None,
    ) -> None:
        self._paths = tuple(Path(path) for path in paths)
        if timestamps is not None and len(timestamps) != len(self._paths):
            raise ValueError("timestamps must have one entry for each frame path")
        self._timestamps = tuple(timestamps) if timestamps is not None else None
        self._index = 0

    def capture(self) -> Frame:
        if self._index >= len(self._paths):
            raise CaptureError("Replay frame sequence is exhausted")

        path = self._paths[self._index]
        try:
            image_bytes = path.read_bytes()
            timestamp = (
                self._timestamps[self._index]
                if self._timestamps is not None
                else datetime.fromtimestamp(path.stat().st_mtime, tz=UTC)
            )
        except OSError as exc:
            raise InvalidFrame(f"Cannot read replay frame {path}: {exc}") from exc

        frame = _validated_frame(image_bytes, timestamp, source=f"replay:{path.name}")
        self._index += 1
        return frame


class AdbScreenshotSource:
    """Request device status and screenshots using read-only ADB commands only."""

    def __init__(
        self,
        adb_path: str = "adb",
        timeout_seconds: float = 10.0,
        device_serial: str | None = None,
        runner: Runner = subprocess.run,
        clock: Clock = lambda: datetime.now(UTC),
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        self._adb_path = adb_path
        self._timeout_seconds = timeout_seconds
        self._device_serial = device_serial
        self._runner = runner
        self._clock = clock

    def capture(self) -> Frame:
        prefix = [self._adb_path]
        if self._device_serial:
            prefix.extend(["-s", self._device_serial])

        try:
            status = self._runner(
                [*prefix, "get-state"],
                capture_output=True,
                timeout=self._timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise CaptureTimeout("Timed out while checking ADB device status") from exc
        except OSError as exc:
            raise DeviceUnavailable(
                f"Could not run ADB executable {self._adb_path!r}: {exc}"
            ) from exc

        if status.returncode != 0 or status.stdout.strip() != b"device":
            raise DeviceUnavailable("No authorized Android device is available through ADB")

        try:
            result = self._runner(
                [*prefix, "exec-out", "screencap", "-p"],
                capture_output=True,
                timeout=self._timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise CaptureTimeout("Timed out while requesting an ADB screenshot") from exc
        except OSError as exc:
            raise DeviceUnavailable(f"ADB screenshot request failed: {exc}") from exc

        if result.returncode != 0:
            raise DeviceUnavailable("ADB could not acquire a screenshot from the device")

        source = f"adb:{self._device_serial}" if self._device_serial else "adb:default-device"
        return _validated_frame(
            result.stdout,
            self._clock(),
            source=source,
            freshness=Freshness.FRESH,
        )
