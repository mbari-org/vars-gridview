from __future__ import annotations

from pathlib import Path


def test_controllers_do_not_import_or_use_qmessagebox() -> None:
    controllers_dir = (
        Path(__file__).resolve().parents[1] / "src" / "vars_gridview" / "controllers"
    )
    assert controllers_dir.is_dir()

    controller_files = sorted(controllers_dir.glob("*.py"))
    assert controller_files, "Expected controller modules to exist"

    violating = []
    for file_path in controller_files:
        text = file_path.read_text(encoding="utf-8")
        if "QMessageBox" in text:
            violating.append(file_path.name)

    assert not violating, f"QMessageBox usage found in controller files: {violating}"
