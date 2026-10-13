import json
import logging

from royale_mind.logging_setup import JsonFormatter


def test_json_formatter_includes_message_and_safe_extra_fields() -> None:
    record = logging.LogRecord(
        name="royale_mind.capture",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="frame acquired",
        args=(),
        exc_info=None,
    )
    record.frame_id = "fixture-1"

    payload = json.loads(JsonFormatter().format(record))

    assert payload["level"] == "INFO"
    assert payload["logger"] == "royale_mind.capture"
    assert payload["message"] == "frame acquired"
    assert payload["frame_id"] == "fixture-1"
