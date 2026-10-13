"""Resolution-independent arena mapping from measured point correspondences."""

from __future__ import annotations

import hashlib
import math
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

from royale_mind.data_acquisition.models import (
    ArenaCalibration,
    ArenaCorrespondence,
    CoordinatePoint,
)


class CalibrationError(ValueError):
    """Calibration cannot be constructed reliably from supplied correspondences."""


def _solve_three_by_three(matrix: list[list[float]], values: list[float]) -> list[float]:
    augmented = [row[:] + [value] for row, value in zip(matrix, values, strict=True)]
    for pivot_index in range(3):
        pivot = max(range(pivot_index, 3), key=lambda row: abs(augmented[row][pivot_index]))
        if abs(augmented[pivot][pivot_index]) < 1e-10:
            raise CalibrationError("Calibration points are collinear or numerically degenerate")
        augmented[pivot_index], augmented[pivot] = augmented[pivot], augmented[pivot_index]
        scale = augmented[pivot_index][pivot_index]
        augmented[pivot_index] = [value / scale for value in augmented[pivot_index]]
        for row_index in range(3):
            if row_index == pivot_index:
                continue
            factor = augmented[row_index][pivot_index]
            augmented[row_index] = [
                value - factor * pivot_value
                for value, pivot_value in zip(
                    augmented[row_index], augmented[pivot_index], strict=True
                )
            ]
    return [augmented[index][3] for index in range(3)]


class ArenaMapper:
    """Fit an affine normalized screenshot-to-arena transform from measured points."""

    def __init__(self, calibration: ArenaCalibration, coefficients: tuple[float, ...]) -> None:
        self.calibration = calibration
        self._x_coefficients = coefficients[:3]
        self._y_coefficients = coefficients[3:]

    def to_arena(self, screenshot_point: CoordinatePoint) -> CoordinatePoint:
        x, y = screenshot_point.x, screenshot_point.y
        arena_x = sum(a * b for a, b in zip(self._x_coefficients, (x, y, 1.0), strict=True))
        arena_y = sum(a * b for a, b in zip(self._y_coefficients, (x, y, 1.0), strict=True))
        if not -1e-6 <= arena_x <= 1.000001 or not -1e-6 <= arena_y <= 1.000001:
            raise CalibrationError("Mapped point falls outside normalized arena coordinates")
        return CoordinatePoint(x=min(1.0, max(0.0, arena_x)), y=min(1.0, max(0.0, arena_y)))


def fit_arena_mapper(
    *,
    screenshot_path: Path,
    width: int,
    height: int,
    correspondences: Sequence[ArenaCorrespondence],
    arena_key: str | None = None,
) -> ArenaMapper:
    if len(correspondences) < 3:
        raise CalibrationError("At least three measured correspondences are required")
    points = [(item.screenshot_point, item.arena_point) for item in correspondences]
    normal = [[0.0] * 3 for _ in range(3)]
    target_x = [0.0] * 3
    target_y = [0.0] * 3
    for source, target in points:
        vector = (source.x, source.y, 1.0)
        for row in range(3):
            target_x[row] += vector[row] * target.x
            target_y[row] += vector[row] * target.y
            for column in range(3):
                normal[row][column] += vector[row] * vector[column]
    x_coefficients = _solve_three_by_three(normal, target_x)
    y_coefficients = _solve_three_by_three(normal, target_y)

    residuals: list[float] = []
    for source, target in points:
        source_vector = (source.x, source.y, 1.0)
        mapped_x = sum(a * b for a, b in zip(x_coefficients, source_vector, strict=True))
        mapped_y = sum(a * b for a, b in zip(y_coefficients, source_vector, strict=True))
        residuals.append(math.hypot(mapped_x - target.x, mapped_y - target.y))
    fit_rmse = math.sqrt(sum(value * value for value in residuals) / len(residuals))
    confidence = math.exp(-fit_rmse / 0.02)
    screenshot_hash = hashlib.sha256(screenshot_path.read_bytes()).hexdigest()
    calibration = ArenaCalibration(
        screenshot_sha256=screenshot_hash,
        screenshot_width=width,
        screenshot_height=height,
        arena_key=arena_key,
        correspondences=list(correspondences),
        mapping_method="least_squares_affine_normalized_v1",
        confidence=confidence,
        fit_rmse=fit_rmse,
        calibrated_at=datetime.now(UTC),
        notes="Confidence is an uncalibrated fit-quality score derived from correspondence RMSE.",
    )
    return ArenaMapper(calibration, tuple(x_coefficients + y_coefficients))
