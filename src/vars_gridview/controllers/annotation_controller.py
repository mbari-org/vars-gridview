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
from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import TYPE_CHECKING
from uuid import UUID

from PyQt6.QtCore import QObject, QThreadPool, pyqtSignal

from vars_gridview.lib.runtime.runnables import Worker
from vars_gridview.services.annotation_service import AnnotationService
from vars_gridview.services.knowledge_base_service import KnowledgeBaseService

if TYPE_CHECKING:
    from vars_gridview.lib.annotation.association import BoundingBoxAssociation

_LOG = logging.getLogger(__name__)

# Per-box writes within one bulk operation run this many at a time: each is
# an independent PUT/DELETE, and one after another a 2,000-box verify spent
# minutes waiting on round trips.
WRITE_CONCURRENCY = 6


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
        # Operations run one at a time, in the order they were started, so a
        # quick Verify-then-Unverify can't finish in the other order.
        self._pool = QThreadPool(self)
        self._pool.setMaxThreadCount(1)

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
        except Exception as exc:  # noqa: BLE001
            self.operation_failed.emit(f"Could not resolve concept '{concept}': {exc}")
            return
        if not canonical:
            # Unknown concept (typo) or knowledge base unreachable: labelling
            # with None would keep the old concept but still mark it verified.
            self.operation_failed.emit(
                f"'{concept}' is not a concept in the knowledge base; nothing was changed."
            )
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

    def verify_and_mark_training_selected(
        self,
        associations: Sequence[BoundingBoxAssociation],
        observer: str | None = None,
    ) -> None:
        """Verify *associations* and mark them for training, as one operation
        with one write per localization (both live in the box JSON)."""
        if not associations:
            return
        desc = f"Verifying and marking {len(associations)} localizations for training"
        self._dispatch(
            desc, self._apply_verified_and_training, list(associations), observer
        )

    # ── Bulk delete ────────────────────────────────────────────────────────────

    def delete_selected(
        self,
        associations: Sequence[BoundingBoxAssociation],
        *,
        delete_dangling_observations: bool = False,
        plan: DeletePlan | None = None,
    ) -> None:
        """Delete *associations* from VARS.

        Args:
            associations: Localizations to delete.
            delete_dangling_observations: Whether to delete observations that
                would otherwise be left with no associations at all.
            plan: The plan already shown to the user (from
                :meth:`plan_delete`); computed here only if not given.
        """
        if not associations:
            return
        if plan is None:
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

        Makes one request per observation: call it off the GUI thread.

        Args:
            associations: Candidate localizations to delete.

        Returns:
            A :class:`DeletePlan` containing observation UUIDs that would end up
            with no remaining associations of any kind. (Deleting an
            observation deletes all its associations -- comments, sample IDs
            -- so one that keeps any of those is not offered for deletion.)
        """
        selected_assoc_uuids = {assoc.uuid for assoc in associations}
        selected_observation_uuids = {assoc.observation.uuid for assoc in associations}

        dangling_observations: set[UUID] = set()
        failures: list[str] = []

        for observation_uuid in selected_observation_uuids:
            try:
                existing = self._annotations.get_observation_association_uuids(
                    observation_uuid
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
        self._pool.start(worker)

    @staticmethod
    def _run_each(
        associations: list[BoundingBoxAssociation],
        write: Callable[[BoundingBoxAssociation], None],
    ) -> list[str]:
        """Apply *write* to every association, WRITE_CONCURRENCY at a time;
        return one failure line per association that raised."""
        failures: list[str] = []

        def one(assoc: BoundingBoxAssociation) -> str | None:
            try:
                write(assoc)
            except Exception as exc:  # noqa: BLE001
                return f"{assoc.uuid}: {exc}"
            return None

        if len(associations) <= 1:
            results = [one(a) for a in associations]
        else:
            with ThreadPoolExecutor(max_workers=WRITE_CONCURRENCY) as pool:
                results = list(pool.map(one, associations))
        failures.extend(r for r in results if r is not None)
        return failures

    def _on_error(self, error: tuple) -> None:
        exc_type, exc_value, _tb = error
        msg = f"{exc_type.__name__}: {exc_value}"
        _LOG.error("Annotation operation failed: %s", msg)
        self.operation_failed.emit(msg)

    # ── Worker functions (run off-thread) ──────────────────────────────────────

    def label_selected_partial(
        self,
        associations: Sequence[BoundingBoxAssociation],
        concept: str | None,
        part: str | None,
        observer: str | None = None,
    ) -> None:
        """Apply concept and/or part to associations; None means leave that field unchanged.

        Args:
            associations: Localizations to label.
            concept: Proposed concept name (canonicalised via KB), or None to leave unchanged.
            part: Proposed part name, or None to leave unchanged.
            observer: VARS user name.  Falls back to the service default.
        """
        if not associations:
            return

        canonical = concept
        if concept is not None:
            try:
                canonical = self._kb.get_concept_name(concept)
            except Exception as exc:  # noqa: BLE001
                self.operation_failed.emit(
                    f"Could not resolve concept '{concept}': {exc}"
                )
                return
            if not canonical:
                self.operation_failed.emit(
                    f"'{concept}' is not a concept in the knowledge base; nothing was changed."
                )
                return
            if canonical != concept:
                self.concept_remapped.emit(concept, canonical)

        label_parts = []
        if canonical is not None:
            label_parts.append(f"'{canonical}'")
        if part is not None:
            label_parts.append(f"part '{part}'")
        desc = f"Labelling {len(associations)} localizations as " + " ".join(
            label_parts
        )
        self._dispatch(
            desc, self._apply_labels, list(associations), canonical, part, observer
        )

    def _apply_labels(
        self,
        associations: list[BoundingBoxAssociation],
        concept: str | None,
        part: str | None,
        observer: str | None,
    ) -> None:
        """Apply concept/part labels and push to VARS.

        Args:
            associations: Localizations to update.
            concept: Canonical concept name, or None to leave unchanged.
            part: Body part, or None to leave unchanged.
            observer: VARS user name.
        """
        verifier = observer or self._annotations.observer

        def write(assoc: BoundingBoxAssociation) -> None:
            assoc.set_verified_concept(concept, part, verifier)
            self._annotations.push_changes(assoc, observer)

        failures = self._run_each(associations, write)

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
        verifier = observer or self._annotations.observer

        def write(assoc: BoundingBoxAssociation) -> None:
            if verified:
                assoc.verify(verifier)
            else:
                assoc.unverify()
            self._annotations.push_changes(assoc, observer)

        failures = self._run_each(associations, write)

        if failures:
            raise RuntimeError(
                "Failed to update verification for "
                f"{len(failures)} of {len(associations)} localizations:\n"
                + "\n".join(failures)
            )

    def _apply_verified_and_training(
        self,
        associations: list[BoundingBoxAssociation],
        observer: str | None,
    ) -> None:
        verifier = observer or self._annotations.observer

        def write(assoc: BoundingBoxAssociation) -> None:
            assoc.verify(verifier)
            assoc.mark_for_training()
            self._annotations.push_changes(assoc, observer)

        failures = self._run_each(associations, write)

        if failures:
            raise RuntimeError(
                "Failed to verify and mark for training "
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

        def write(assoc: BoundingBoxAssociation) -> None:
            if for_training:
                assoc.mark_for_training()
            else:
                assoc.unmark_for_training()
            self._annotations.push_changes(assoc, observer)

        failures = self._run_each(associations, write)

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
