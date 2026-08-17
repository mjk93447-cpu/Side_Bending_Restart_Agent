"""Frozen vs source app paths and bundled Tesseract lookup."""

from pathlib import Path

from src.paths import APP_VERSION, app_root, default_config_path, find_tesseract_exe, logs_dir


def test_app_root_is_repo_in_source_checkout() -> None:
    root = app_root()
    assert (root / "config.yaml").exists()
    assert (root / "src" / "app.py").exists()


def test_default_config_and_logs_live_under_app_root() -> None:
    assert default_config_path() == app_root() / "config.yaml"
    assert logs_dir() == app_root() / "logs"


def test_find_tesseract_prefers_app_root_bundle(tmp_path: Path, monkeypatch) -> None:
    bundled = tmp_path / "tesseract" / "tesseract.exe"
    bundled.parent.mkdir(parents=True)
    bundled.write_bytes(b"fake")
    monkeypatch.setattr("src.paths.app_root", lambda: tmp_path)
    monkeypatch.delenv("TESSERACT_CMD", raising=False)
    assert find_tesseract_exe() == bundled.resolve()


def test_find_tesseract_uses_env_override(tmp_path: Path, monkeypatch) -> None:
    exe = tmp_path / "custom" / "tesseract.exe"
    exe.parent.mkdir()
    exe.write_bytes(b"fake")
    monkeypatch.setattr("src.paths.app_root", lambda: tmp_path / "empty")
    monkeypatch.setenv("TESSERACT_CMD", str(exe))
    assert find_tesseract_exe() == exe.resolve()


def test_app_version_is_semver() -> None:
    parts = APP_VERSION.split(".")
    assert len(parts) == 3
    assert all(p.isdigit() for p in parts)
