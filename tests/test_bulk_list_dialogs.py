"""Long lists in the query dialog: pasting past the old 32,767-character
cap, opening a text file, and staying fast with tens of thousands."""

from __future__ import annotations

import time
import uuid

import pytest
from PyQt6 import QtCore, QtWidgets

from vars_gridview.ui.dialogs.query_dialog import (
    BulkUUIDInputDialog,
    BulkValidatedInputDialog,
    ConceptInConstraintResult,
    UUIDInConstraintResult,
)

_app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


@pytest.fixture
def warnings(monkeypatch) -> list[str]:
    shown: list[str] = []
    monkeypatch.setattr(
        QtWidgets.QMessageBox, "warning", lambda _p, _t, text: shown.append(text)
    )
    return shown


def _pick(monkeypatch, path) -> None:
    monkeypatch.setattr(
        QtWidgets.QFileDialog,
        "getOpenFileName",
        lambda *a, **k: (str(path), ""),
    )


def test_open_file_of_forty_thousand_uuids(tmp_path, monkeypatch, warnings) -> None:
    uuids = [str(uuid.uuid4()).upper() for _ in range(40_000)]
    path = tmp_path / "uuids.csv"
    # A header, a repeat, quotes, blank lines and Windows line ends.
    lines = ["association_uuid", *uuids, uuids[0], f'"{uuids[1]}"', ""]
    path.write_bytes(("﻿" + "\r\n".join(lines)).encode())
    _pick(monkeypatch, path)

    dialog = BulkUUIDInputDialog()
    start = time.perf_counter()
    dialog.open_file()
    elapsed = time.perf_counter() - start

    assert dialog.items() == uuids
    assert elapsed < 2.0
    assert len(warnings) == 1 and "association_uuid" in warnings[0]
    assert "40,000" in dialog._count_label.text()


def test_paste_more_than_the_old_cap(warnings) -> None:
    uuids = [str(uuid.uuid4()) for _ in range(5_000)]  # ~185,000 characters
    dialog = BulkUUIDInputDialog()
    dialog._input.setText("\n".join(uuids))
    dialog.add_items()
    assert dialog.items() == uuids
    assert warnings == []


def test_file_adds_to_what_was_typed(tmp_path, monkeypatch, warnings) -> None:
    a, b = str(uuid.uuid4()), str(uuid.uuid4())
    dialog = BulkUUIDInputDialog()
    dialog._input.setText(a)
    dialog.add_items()
    path = tmp_path / "more.txt"
    path.write_text(f"{a}\n{b}\n")
    _pick(monkeypatch, path)
    dialog.open_file()
    assert dialog.items() == [a, b]


def test_delete_selected_from_a_long_list(warnings) -> None:
    uuids = [str(uuid.uuid4()) for _ in range(20_000)]
    dialog = BulkUUIDInputDialog()
    dialog.add_values(uuids)
    model = dialog._list.model()
    dialog._list.selectionModel().select(  # shift-click rows 5,000 to 14,999
        QtCore.QItemSelection(model.index(5_000, 0), model.index(14_999, 0)),
        QtCore.QItemSelectionModel.SelectionFlag.Select,
    )
    start = time.perf_counter()
    dialog.delete_selected_items()
    assert time.perf_counter() - start < 2.0
    assert dialog.items() == uuids[:5_000] + uuids[15_000:]
    dialog.add_values([uuids[5_000]])  # deleted, so it can come back
    assert dialog.items()[-1] == uuids[5_000]


def test_cancelled_file_picker_adds_nothing(monkeypatch, warnings) -> None:
    monkeypatch.setattr(
        QtWidgets.QFileDialog, "getOpenFileName", lambda *a, **k: ("", "")
    )
    dialog = BulkUUIDInputDialog()
    dialog.open_file()
    assert dialog.items() == []


def test_concept_file_one_per_line(tmp_path, monkeypatch, warnings) -> None:
    known = ["Sebastes", "Sebastes melanops", "Pyrosoma atlanticum"]
    path = tmp_path / "concepts.txt"
    path.write_text("Sebastes melanops\npyrosoma atlanticum\nNot a thing\n\n")
    _pick(monkeypatch, path)
    dialog = BulkValidatedInputDialog(values_getter=lambda: known, item_label="Concept")
    dialog.open_file()
    # Names keep their spaces; case is matched to the knowledge base.
    assert dialog.items() == ["Sebastes melanops", "Pyrosoma atlanticum"]
    assert len(warnings) == 1 and "Not a thing" in warnings[0]


def test_long_lists_are_summarised_in_the_query() -> None:
    concepts = ConceptInConstraintResult(
        "Concepts", [f"c{i}" for i in range(3_000)], "concept"
    )
    assert str(concepts).endswith("… (3,000 in all)")
    uuids = UUIDInConstraintResult("Association UUID", ["x"] * 40_000, "a")
    assert str(uuids) == "Association UUID: (40,000 items)"
