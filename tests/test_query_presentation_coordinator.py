from __future__ import annotations

from vars_gridview.ui.coordinators import query_presentation_coordinator as qpc


class _FakeDialog:
    def __init__(self, *_args, **_kwargs) -> None:
        self._maximum = 0
        self._value = 0
        self._label = ""
        self.closed = False

    def setWindowTitle(self, _title: str) -> None:
        pass

    def setWindowModality(self, _modality) -> None:
        pass

    def setMinimumDuration(self, _duration: int) -> None:
        pass

    def setValue(self, value: int) -> None:
        self._value = value

    def value(self) -> int:
        return self._value

    def setMaximum(self, maximum: int) -> None:
        self._maximum = maximum

    def maximum(self) -> int:
        return self._maximum

    def setLabelText(self, text: str) -> None:
        self._label = text

    def labelText(self) -> str:
        return self._label

    def show(self) -> None:
        pass

    def close(self) -> None:
        self.closed = True


def test_query_presentation_lifecycle(monkeypatch) -> None:
    monkeypatch.setattr(qpc.QtWidgets, "QProgressDialog", _FakeDialog)

    status_updates = []
    coordinator = qpc.QueryPresentationCoordinator(
        parent=None,
        dialog_parent=None,
        status_update_callback=lambda state: status_updates.append(state),
    )

    coordinator.on_query_started()
    coordinator.on_query_progress("Downloading", 2, 6)
    coordinator.mark_rendering()
    coordinator.mark_done()

    assert status_updates == []


def test_query_failed_updates_status_and_shows_error(monkeypatch) -> None:
    monkeypatch.setattr(qpc.QtWidgets, "QProgressDialog", _FakeDialog)

    errors = []
    monkeypatch.setattr(
        qpc.QtWidgets.QMessageBox,
        "critical",
        lambda *_args, **_kwargs: errors.append(True),
    )

    status_updates = []
    coordinator = qpc.QueryPresentationCoordinator(
        parent=None,
        dialog_parent=None,
        status_update_callback=lambda state: status_updates.append(state),
    )

    coordinator.on_query_started()
    coordinator.on_query_failed("boom")

    assert status_updates == [{"Status": "Query failed"}]
    assert errors == [True]
