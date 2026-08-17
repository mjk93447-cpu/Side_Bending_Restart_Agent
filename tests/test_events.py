"""JSONL event log."""

from pathlib import Path

from src.events import EventLog


def test_event_log_appends_json_lines(tmp_path: Path) -> None:
    path = tmp_path / "events.jsonl"
    log = EventLog(path)
    log.write({"type": "scan", "nan_count": 3})
    log.write({"type": "recovery_start"})
    lines = path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    assert '"scan"' in lines[0]
    assert '"nan_count": 3' in lines[0]
    assert '"recovery_start"' in lines[1]
    assert '"ts"' in lines[0]
