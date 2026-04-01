"""Coordinator for persisting dirty annotation associations off the UI thread."""

from __future__ import annotations

from typing import Callable
from uuid import UUID

from PyQt6 import QtCore


class DirtyAssociationSaveCoordinator(QtCore.QObject):
    """Own model-only persistence logic shared by multiple UI workflows."""

    def __init__(
        self,
        *,
        parent: QtCore.QObject,
        annotation_service_getter: Callable[[], object | None],
    ) -> None:
        super().__init__(parent)
        self._annotation_service_getter = annotation_service_getter

    def save_dirty_associations_worker(self, associations: list) -> set[UUID]:
        """Persist dirty associations in a worker thread.

        This function intentionally operates only on model objects.
        """
        annotation_service = self._annotation_service_getter()
        if annotation_service is None:
            raise RuntimeError("Annotation service is unavailable")

        saved: set[UUID] = set()
        failures: list[str] = []
        for assoc in associations:
            try:
                annotation_service.push_changes(assoc)
                saved.add(assoc.uuid)
            except Exception as exc:  # noqa: BLE001
                failures.append(f"{assoc.uuid}: {exc}")

        if failures:
            raise RuntimeError(
                "Failed to save one or more localizations before selection change:\n"
                + "\n".join(failures)
            )
        return saved


__all__ = ["DirtyAssociationSaveCoordinator"]
