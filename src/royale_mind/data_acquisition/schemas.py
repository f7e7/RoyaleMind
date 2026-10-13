"""Export JSON Schema documents from the validated Pydantic acquisition models."""

import json
from pathlib import Path

from pydantic import BaseModel

from royale_mind.data_acquisition.models import (
    ArenaCalibration,
    ArenaDefinition,
    CardRecord,
    DataProvenance,
    DatasetInspection,
    VisualAnnotation,
)

SCHEMAS: dict[str, type[BaseModel]] = {
    "card-record": CardRecord,
    "data-provenance": DataProvenance,
    "arena-definition": ArenaDefinition,
    "arena-calibration": ArenaCalibration,
    "dataset-inspection": DatasetInspection,
    "visual-annotation": VisualAnnotation,
}


def export_schemas(output_directory: Path) -> list[Path]:
    output_directory.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for name, model in SCHEMAS.items():
        path = output_directory / f"{name}.schema.json"
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(model.model_json_schema(), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        temporary.replace(path)
        written.append(path)
    return written
