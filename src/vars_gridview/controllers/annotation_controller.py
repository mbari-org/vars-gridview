"""Annotation controller — bulk label / verify / train / delete operations.

:class:`AnnotationController` translates UI bulk actions (e.g. "label
selected to concept X") into one or more :class:`~vars_gridview.services.annotation_service.AnnotationService`
calls executed on a thread-pool worker.

It is deliberately thin:

* **Validation** of concept / part names against the knowledge base is done
  here before any I/O begins.
* **Per-association mutations** are delegated to :class:`~vars_gridview.services.annotation_service.AnnotationService`.
* **UI feedback** flows back through typed Qt signals so widgets don't need to
  know anything about the service layer.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Sequence
from uuid import UUID

from PyQt6.QtCore import QObject, QThreadPool, pyqtSignal

from vars_gridview.lib.runnables import Worker
from vars_gridview.services.annotation_service import AnnotationService
from vars_gridview.services.knowledge_base_service import KnowledgeBaseService

if TYPE_CHECKING:
    from vars_gridview.lib.association import BoundingBoxAssociation

_LOG = logging.getLogger(__name__)


@dataclass(frozen=True)
class DeletePlan:
    """Summary of a proposed bulk delete operation."""

    dangling_observation_uuids: set[UUID]

    @property
    def dangling_count(self) -> int:
        """Number of observations that would become box-less after delete."""
        return len(self.dangling_observation_uuids)


class AnnotationController(QObject):
    """Controller for bulk annotation mutations.

    Signals:
        operation_started: Emitted when a bulk operation begins.  The argument
            is a short description string (e.g. ``"Labelling 5 localizations"``).
        operation_finished: Emitted when a bulk operation completes
            successfully.  The argument is the description from
            :attr:`operation_started`.
        operation_failed: Emitted when a bulk operation raises an exception.
            The argument is a human-readable error message.
        concept_remapped: Emitted when a concept name is aliased to its
            canonical form.  Arguments are ``(original, canonical)``.
    """

    operation_started = pyqtSignal(str)
    operation_failed = pyqtSignal(str)
    operation_finished = pyqtSignal(str)
    concept_remapped = pyqtSignal(str, str)  # (original, canonical)

    def __init__(
        self,
        annotation_service: AnnotationService,
        knowledge_base_service: KnowledgeBaseService,
        parent: QObject | None = None,
    ) -> None:
        """Initialise the controller.

        Args:
            annotation_service: Service used to push mutations to VARS.
            knowledge_base_service: Service used to validate concepts / parts.
            parent: Optional Qt parent.
        """
        super().__init__(parent)
        self._annotations = annotation_service
        self._kb = knowledge_base_service

    # ── Bulk label ─────────────────────────────────────────────────────────────

    def label_selected(
        self,
        associations: Sequence[BoundingBoxAssociation],
        concept: str,
        part: str,
        observer: str | None = None,
    ) -> None:
        """Apply *concept* and *part* to *associations* and push to VARS.

        The concept is resolved through the knowledge base (name aliasing).
        The call is asynchronous — progress is reported via signals.

        Args:
            associations: Localizations to label.
            concept: Proposed concept name (will be canonicalised).
            part: Proposed part name (use ``"self"`` for whole animal).
            observer: VARS user name.  Falls back to the service default.
        """
        if not associations:
            return

        try:
            canonical = self._kb.get_concept_name(concept)
        except Exception as exc:
            self.operation_failed.emit(f"Could not resolve concept '{concept}': {exc}")
            return

        if canonical != concept:
            self.concept_remapped.emit(concept, canonical)

        desc = f"Labelling {len(associations)} localizations as '{canonical}'"
        self._dispatch(
            desc, self._apply_labels, list(associations), canonical, part, observer
        )

    # ── Bulk verify ────────────────────────────────────────────────────────────

    def verify_selected(
        self,
        associations: Sequence[BoundingBoxAssociation],
        verified: bool,
        observer: str | None = None,
    ) -> None:
        """Set the verification flag on *associations*.

        Args:
            associations: Localizations to (un)verify.
            verified: ``True`` to verify, ``False`` to unverify.
            observer: VARS user name.  Falls back to the service default.
        """
        if not associations:
            return
        verb = "Verifying" if verified else "Unverifying"
        desc = f"{verb} {len(associations)} localizations"
        self._dispatch(
            desc, self._apply_verified, list(associations), verified, observer
        )

    # ── Bulk training flag ─────────────────────────────────────────────────────

    def mark_training_selected(
        self,
        associations: Sequence[BoundingBoxAssociation],
        for_training: bool,
        observer: str | None = None,
    ) -> None:
        """Set the training flag on *associations*.

        Args:
            associations: Localizations to (un)mark.
            for_training: ``True`` to mark for training, ``False`` to unmark.
            observer: VARS user name.  Falls back to the service default.
        """
        if not associations:
            return
        verb = "Marking" if for_training else "Unmarking"
        desc = f"{verb} {len(associations)} localizations for training"
        self._dispatch(
            desc, self._apply_training, list(associations), for_training, observer
        )

    # ── Bulk delete ────────────────────────────────────────────────────────────

    def delete_selected(
        self,
        associations: Sequence[BoundingBoxAssociation],
        *,
        delete_dangling_observations: bool = False,
    ) -> None:
        """Delete *associations* from VARS.

        Args:
            associations: Localizations to delete.
            delete_dangling_observations: Whether to delete observations that
                would otherwise be left with no bounding-box associations.
        """
        if not associations:
            return
        plan = self.plan_delete(associations)
        desc = f"Deleting {len(associations)} localizations"
        if delete_dangling_observations and plan.dangling_count > 0:
            desc += f" and {plan.dangling_count} dangling observations"
        self._dispatch(
            desc,
            self._apply_delete,
            list(associations),
            plan.dangling_observation_uuids if delete_dangling_observations else set(),
        )

    def plan_delete(
        self,
        associations: Sequence[BoundingBoxAssociation],
    ) -> DeletePlan:
        """Compute dangling observations for a proposed association delete.

        Args:
            associations: Candidate localizations to delete.

        Returns:
            A :class:`DeletePlan` containing observation UUIDs that would end up
            with no remaining bounding-box associations.
        """
        selected_assoc_uuids = {assoc.uuid for assoc in associations}
        selected_observation_uuids = {assoc.observation.uuid for assoc in associations}

        dangling_observations: set[UUID] = set()
        failures: list[str] = []

        for observation_uuid in selected_observation_uuids:
            try:
                existing = (
                    self._annotations.get_observation_bounding_box_association_uuids(
                        observation_uuid
                    )
                )
            except Exception as exc:  # noqa: BLE001
                failures.append(f"{observation_uuid}: {exc}")
                continue

            if len(existing - selected_assoc_uuids) == 0:
                dangling_observations.add(observation_uuid)

        if failures:
            raise RuntimeError(
                "Failed to inspect one or more observations for delete planning:\n"
                + "\n".join(failures)
            )

        return DeletePlan(dangling_observation_uuids=dangling_observations)

    # ── Dispatch helper ────────────────────────────────────────────────────────

    def _dispatch(self, description: str, fn, *args) -> None:
        """Run *fn* in a thread-pool worker with progress signals.

        Args:
            description: Human-readable summary emitted with :attr:`operation_started`.
            fn: Callable to run off the main thread.
            *args: Positional arguments forwarded to *fn*.
        """
        self.operation_started.emit(description)
        worker = Worker(fn, *args)
        worker.signals.result.connect(
            lambda _: self.operation_finished.emit(description)
        )
        worker.signals.error.connect(self._on_error)
        QThreadPool.globalInstance().start(worker)

    def _on_error(self, error: tuple) -> None:
        exc_type, exc_value, _tb = error
        msg = f"{exc_type.__name__}: {exc_value}"
        _LOG.error("Annotation operation failed: %s", msg)
        self.operation_failed.emit(msg)

    # ── Worker functions (run off-thread) ──────────────────────────────────────

    def _apply_labels(
        self,
        associations: list[BoundingBoxAssociation],
        concept: str,
        part: str,
        observer: str | None,
    ) -> None:
        """Apply concept/part labels and push to VARS.

        Args:
            associations: Localizations to update.
            concept: Canonical concept name.
            part: Body part (``"self"`` for whole animal).
            observer: VARS user name.
        """
        failures: list[str] = []
        for assoc in associations:
            assoc.set_verified_concept(
                concept, part, observer or self._annotations.observer
            )
            try:
                self._annotations.push_changes(assoc, observer)
            except Exception as exc:  # noqa: BLE001
                failures.append(f"{assoc.uuid}: {exc}")

        if failures:
            raise RuntimeError(
                "Failed to label "
                f"{len(failures)} of {len(associations)} localizations:\n"
                + "\n".join(failures)
            )

    def _apply_verified(
        self,
        associations: list[BoundingBoxAssociation],
        verified: bool,
        observer: str | None,
    ) -> None:
        """Set verification flag and push to VARS.

        Args:
            associations: Localizations to update.
            verified: New verification state.
            observer: VARS user name.
        """
        failures: list[str] = []
        for assoc in associations:
            if verified:
                assoc.verify(observer or self._annotations.observer)
            else:
                assoc.unverify()
            try:
                self._annotations.push_changes(assoc, observer)
            except Exception as exc:  # noqa: BLE001
                failures.append(f"{assoc.uuid}: {exc}")

        if failures:
            raise RuntimeError(
                "Failed to update verification for "
                f"{len(failures)} of {len(associations)} localizations:\n"
                + "\n".join(failures)
            )

    def _apply_training(
        self,
        associations: list[BoundingBoxAssociation],
        for_training: bool,
        observer: str | None,
    ) -> None:
        """Set training flag and push to VARS.

        Args:
            associations: Localizations to update.
            for_training: New training state.
            observer: VARS user name.
        """
        failures: list[str] = []
        for assoc in associations:
            if for_training:
                assoc.mark_for_training()
            else:
                assoc.unmark_for_training()
            try:
                self._annotations.push_changes(assoc, observer)
            except Exception as exc:  # noqa: BLE001
                failures.append(f"{assoc.uuid}: {exc}")

        if failures:
            raise RuntimeError(
                "Failed to update training flags for "
                f"{len(failures)} of {len(associations)} localizations:\n"
                + "\n".join(failures)
            )

    def _apply_delete(
        self,
        associations: list[BoundingBoxAssociation],
        dangling_observation_uuids: set[UUID] | None = None,
    ) -> None:
        """Delete associations from VARS.

        Args:
            associations: Localizations to delete.
            dangling_observation_uuids: Observation UUIDs to delete instead of
                individual associations.
        """
        dangling_observation_uuids = dangling_observation_uuids or set()
        failures: list[str] = []
        deleted_observations: set[UUID] = set()
        for assoc in associations:
            try:
                observation_uuid = assoc.observation.uuid
                if observation_uuid in dangling_observation_uuids:
                    if observation_uuid not in deleted_observations:
                        self._annotations.delete_observation(observation_uuid)
                        deleted_observations.add(observation_uuid)
                    assoc.deleted = True
                else:
                    self._annotations.delete_association(assoc)
            except Exception as exc:  # noqa: BLE001
                failures.append(f"{assoc.uuid}: {exc}")

        if failures:
            raise RuntimeError(
                "Failed to delete "
                f"{len(failures)} of {len(associations)} localizations:\n"
                + "\n".join(failures)
            )


__all__ = ["AnnotationController", "DeletePlan"]
