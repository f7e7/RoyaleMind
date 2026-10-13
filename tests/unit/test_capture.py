import subprocess
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image

from royale_mind.capture import (
    AdbScreenshotSource,
    CaptureError,
    CaptureTimeout,
    DeviceUnavailable,
    InvalidFrame,
    ReplayFrameSource,
)

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def png_bytes(size: tuple[int, int] = (32, 24)) -> bytes:
    image_buffer = BytesIO()
    Image.new("RGB", size, color=(10, 20, 30)).save(image_buffer, format="PNG")
    return image_buffer.getvalue()


def test_replay_returns_validated_frame_with_supplied_timestamp(tmp_path: Path) -> None:
    image_path = tmp_path / "sample.png"
    image_path.write_bytes(png_bytes())
    source = ReplayFrameSource([image_path], timestamps=[NOW])

    frame = source.capture()

    assert frame.metadata.captured_at == NOW
    assert frame.metadata.width == 32
    assert frame.metadata.height == 24
    assert frame.metadata.source == "replay:sample.png"
    assert frame.metadata.freshness.value == "unknown"
    assert frame.image_format == "PNG"
    assert frame.image_bytes == image_path.read_bytes()


def test_replay_reports_missing_invalid_and_exhausted_frames(tmp_path: Path) -> None:
    missing_source = ReplayFrameSource([tmp_path / "missing.png"])
    with pytest.raises(InvalidFrame, match="Cannot read replay frame"):
        missing_source.capture()

    invalid_path = tmp_path / "invalid.png"
    invalid_path.write_bytes(b"not an image")
    invalid_source = ReplayFrameSource([invalid_path])
    with pytest.raises(InvalidFrame, match="not a valid supported image"):
        invalid_source.capture()

    unsupported_path = tmp_path / "unsupported.gif"
    image_buffer = BytesIO()
    Image.new("RGB", (4, 4)).save(image_buffer, format="GIF")
    unsupported_path.write_bytes(image_buffer.getvalue())
    unsupported_source = ReplayFrameSource([unsupported_path])
    with pytest.raises(InvalidFrame, match="Unsupported screenshot image format"):
        unsupported_source.capture()

    valid_path = tmp_path / "valid.png"
    valid_path.write_bytes(png_bytes())
    exhausted_source = ReplayFrameSource([valid_path], timestamps=[NOW])
    exhausted_source.capture()
    with pytest.raises(CaptureError, match="exhausted"):
        exhausted_source.capture()


def test_replay_requires_timestamp_count_to_match_paths(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="one entry"):
        ReplayFrameSource([tmp_path / "frame.png"], timestamps=[])


def test_replay_rejects_naive_timestamps(tmp_path: Path) -> None:
    image_path = tmp_path / "sample.png"
    image_path.write_bytes(png_bytes())
    source = ReplayFrameSource([image_path], timestamps=[datetime(2026, 1, 1)])

    with pytest.raises(InvalidFrame, match="timezone information"):
        source.capture()


def test_adb_capture_uses_only_status_and_screenshot_commands() -> None:
    commands: list[list[str]] = []

    def runner(command: list[str], **kwargs) -> subprocess.CompletedProcess[bytes]:
        commands.append(command)
        output = b"device" if command[-1] == "get-state" else png_bytes()
        return subprocess.CompletedProcess(command, 0, stdout=output, stderr=b"")

    frame = AdbScreenshotSource(
        device_serial="device-123",
        runner=runner,
        clock=lambda: NOW,
    ).capture()

    assert frame.metadata.source == "adb:device-123"
    assert frame.metadata.captured_at == NOW
    assert frame.metadata.freshness.value == "fresh"
    assert commands == [
        ["adb", "-s", "device-123", "get-state"],
        ["adb", "-s", "device-123", "exec-out", "screencap", "-p"],
    ]


def test_adb_maps_disconnect_and_timeouts_to_typed_errors() -> None:
    def disconnected(command: list[str], **kwargs) -> subprocess.CompletedProcess[bytes]:
        return subprocess.CompletedProcess(command, 1, stdout=b"", stderr=b"no device")

    with pytest.raises(DeviceUnavailable):
        AdbScreenshotSource(runner=disconnected).capture()

    def timed_out(command: list[str], **kwargs) -> subprocess.CompletedProcess[bytes]:
        raise subprocess.TimeoutExpired(command, kwargs["timeout"])

    with pytest.raises(CaptureTimeout, match="checking ADB"):
        AdbScreenshotSource(runner=timed_out).capture()

    call_count = 0

    def screenshot_timed_out(command: list[str], **kwargs) -> subprocess.CompletedProcess[bytes]:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return subprocess.CompletedProcess(command, 0, stdout=b"device", stderr=b"")
        raise subprocess.TimeoutExpired(command, kwargs["timeout"])

    with pytest.raises(CaptureTimeout, match="requesting an ADB screenshot"):
        AdbScreenshotSource(runner=screenshot_timed_out).capture()


def test_adb_rejects_empty_screenshot_bytes() -> None:
    def empty_screenshot(command: list[str], **kwargs) -> subprocess.CompletedProcess[bytes]:
        output = b"device" if command[-1] == "get-state" else b""
        return subprocess.CompletedProcess(command, 0, stdout=output, stderr=b"")

    with pytest.raises(InvalidFrame, match="no image bytes"):
        AdbScreenshotSource(runner=empty_screenshot).capture()
