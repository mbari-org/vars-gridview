"""Coordinate annotation actions initiated from MainWindow UI flows."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from PyQt6 import QtCore, QtWidgets

from vars_gridview.lib.config.constants import get_settings
from vars_gridview.lib.config.settings import AppSettings
from vars_gridview.lib.runtime.runnables import Worker

if TYPE_CHECKING:
    from vars_gridview.controllers.annotation_controller import AnnotationController
    from vars_gridview.services.knowledge_base_service import KnowledgeBaseService
    from vars_gridview.ui.mosaic.image_mosaic import ImageMosaic
    from vars_gridview.ui.mosaic.rect_widget import RectWidget


class AnnotationActionCoordinator:
    """Encapsulate annotation action dispatch and confirmation flows."""

    def __init__(
        self,
        parent: QtWidgets.QWidget,
        image_mosaic: ImageMosaic,
        annotation_controller_getter: Callable[[], AnnotationController | None],
        kb_service_getter: Callable[[], KnowledgeBaseService | None],
        settings: AppSettings | None = None,
    ) -> None:
        self._parent = parent
        self._image_mosaic = image_mosaic
        self._annotation_controller_getter = annotation_controller_getter
        self._kb_service_getter = kb_service_getter
        self._settings = settings or get_settings()
        self._pending_action: str | None = None
        self._pending_deleted_rects: list[RectWidget] = []

    @property
    def pending_action(self) -> str | None:
        return self._pending_action

    def consume_pending_deleted_rects(self) -> list[RectWidget]:
        rects = list(self._pending_deleted_rects)
        self._pending_deleted_rects = []
        return rects

    def clear_pending(self) -> None:
        self._pending_action = None
        self._pending_deleted_rects = []

    def _busy(self) -> bool:
        """True (and tell the user) while an earlier operation is still
        running: the finish handling is per operation, and a second action
        on top of a running one used to race it."""
        if self._pending_action is None:
            return False
        QtWidgets.QMessageBox.information(
            self._parent,
            "Operation in progress",
            "Please wait for the current operation to finish.",
        )
        return True

    def _controller(self) -> AnnotationController | None:
        return self._annotation_controller_getter()

    def _kb_service(self) -> KnowledgeBaseService | None:
        return self._kb_service_getter()

    def _ensure_annotation_ready(self) -> bool:
        if self._controller() is not None:
            return True
        QtWidgets.QMessageBox.critical(
            self._parent,
            "Not Ready",
            "Annotation services are not initialized.",
        )
        return False

    def _selected_associations(self) -> tuple[list[RectWidget], list]:
        selected_rects = self._image_mosaic.get_selected()
        return selected_rects, [rw.association for rw in selected_rects]

    @staticmethod
    def _confirm_count_action(
        parent: QtWidgets.QWidget,
        title: str,
        message: str,
        count: int,
    ) -> bool:
        if count <= 1:
            return True
        opt = QtWidgets.QMessageBox.question(
            parent,
            title,
            message.format(count=count),
            defaultButton=QtWidgets.QMessageBox.StandardButton.Yes,
        )
        return opt == QtWidgets.QMessageBox.StandardButton.Yes

    def _run_selected_annotation_action(
        self,
        *,
        action_key: str,
        confirm_title: str,
        confirm_message: str,
        run_action: Callable[[list], None],
    ) -> None:
        if not self._ensure_annotation_ready() or self._busy():
            return

        selected_rects, associations = self._selected_associations()
        if not selected_rects:
            return
        if not self._confirm_count_action(
            self._parent,
            confirm_title,
            confirm_message,
            len(selected_rects),
        ):
            return

        self._pending_action = action_key
        run_action(associations)

    def _dispatch_delete(self, selected_rects: list[RectWidget]) -> None:
        controller = self._controller()
        if controller is None:
            return

        associations = [rw.association for rw in selected_rects]
        # Planning makes one request per observation: off the GUI thread.
        # Marked pending now so no other action starts meanwhile.
        self._pending_action = "delete"
        worker = Worker(controller.plan_delete, associations)
        worker.signals.result.connect(
            lambda plan: self._continue_delete(selected_rects, associations, plan)
        )
        worker.signals.error.connect(self._on_delete_plan_failed)
        QtCore.QThreadPool.globalInstance().start(worker)

    def _on_delete_plan_failed(self, err: tuple) -> None:
        self.clear_pending()
        message = str(err[1]) if len(err) > 1 else "Unknown error"
        QtWidgets.QMessageBox.critical(
            self._parent,
            "Delete Planning Failed",
            f"Could not inspect parent observations before delete:\n\n{message}",
        )

    def _continue_delete(self, selected_rects, associations, delete_plan) -> None:
        controller = self._controller()
        if controller is None:
            self.clear_pending()
            return
        delete_dangling_observations = False
        if delete_plan.dangling_count > 0:
            confirm = QtWidgets.QMessageBox.question(
                self._parent,
                "Delete dangling observations?",
                (
                    "This operation would leave "
                    f"{delete_plan.dangling_count} observations with no "
                    "associations at all. Delete those observations too?"
                ),
            )
            delete_dangling_observations = (
                confirm == QtWidgets.QMessageBox.StandardButton.Yes
            )

        self._pending_action = "delete"
        self._pending_deleted_rects = list(selected_rects)
        controller.delete_selected(
            associations,
            delete_dangling_observations=delete_dangling_observations,
            plan=delete_plan,
        )

    def label_selected(self, concept: str, part: str) -> None:
        controller = self._controller()
        if controller is None:
            self._ensure_annotation_ready()
            return
        self._run_selected_annotation_action(
            action_key="label",
            confirm_title="Confirm Label",
            confirm_message=(
                "Label {count} localizations as "
                + f"'{concept}'"
                + (f" with part '{part}'" if part != "self" else "")
                + "?"
            ),
            run_action=lambda associations: controller.label_selected(
                associations,
                concept,
                part,
                self._settings.username.value,
            ),
        )

    def label_selected_quick(self, concept: str, part: str) -> None:
        """Label selected ROIs using a quick-label favorite.

        Blank concept/part means leave that field unchanged on the ROI.
        """
        effective_concept = concept.strip() or None
        effective_part = part.strip() or None

        if effective_concept is None and effective_part is None:
            return

        controller = self._controller()
        if controller is None:
            self._ensure_annotation_ready()
            return

        label_parts = []
        if effective_concept is not None:
            label_parts.append(f"'{effective_concept}'")
        if effective_part is not None:
            label_parts.append(f"part '{effective_part}'")
        confirm_suffix = " ".join(label_parts)

        self._run_selected_annotation_action(
            action_key="label",
            confirm_title="Confirm Quick Label",
            confirm_message=f"Label {{count}} localizations as {confirm_suffix}?",
            run_action=lambda associations: controller.label_selected_partial(
                associations,
                effective_concept,
                effective_part,
                self._settings.username.value,
            ),
        )

    def verify_selected(self, state: bool) -> None:
        controller = self._controller()
        if controller is None:
            self._ensure_annotation_ready()
            return
        action_key = "verify" if state else "unverify"
        confirm_title = "Confirm Verification" if state else "Confirm Unverification"
        confirm_message = (
            "Verify {count} localizations?"
            if state
            else "Unverify {count} localizations?"
        )
        self._run_selected_annotation_action(
            action_key=action_key,
            confirm_title=confirm_title,
            confirm_message=confirm_message,
            run_action=lambda associations: controller.verify_selected(
                associations,
                state,
                self._settings.username.value,
            ),
        )

    def mark_training_selected(self, state: bool) -> None:
        controller = self._controller()
        if controller is None:
            self._ensure_annotation_ready()
            return
        action_key = "mark_training" if state else "unmark_training"
        confirm_title = "Confirm Mark Training" if state else "Confirm Unmark Training"
        confirm_message = (
            "Mark {count} localizations for training?"
            if state
            else "Unmark {count} localizations for training?"
        )
        self._run_selected_annotation_action(
            action_key=action_key,
            confirm_title=confirm_title,
            confirm_message=confirm_message,
            run_action=lambda associations: controller.mark_training_selected(
                associations,
                state,
                self._settings.username.value,
            ),
        )

    def delete_selected(self) -> None:
        if not self._ensure_annotation_ready() or self._busy():
            return

        to_delete = self._image_mosaic.get_selected()
        if not to_delete:
            return

        opt = QtWidgets.QMessageBox.question(
            self._parent,
            "Confirm Deletion",
            f"Delete {len(to_delete)} localizations?\nThis operation cannot be undone.",
            defaultButton=QtWidgets.QMessageBox.StandardButton.No,
        )
        if opt == QtWidgets.QMessageBox.StandardButton.Yes:
            self._dispatch_delete(to_delete)

    def change_concept_from_box(
        self,
        rect_widget: RectWidget,
        current_concept: str,
    ) -> str | None:
        _ = current_concept
        if not self._ensure_annotation_ready():
            return None

        kb_service = self._kb_service()
        if kb_service is None:
            QtWidgets.QMessageBox.critical(
                self._parent,
                "Not Ready",
                "Knowledge base service is not initialized.",
            )
            return None
        kb_concepts = list(kb_service.get_concepts().keys())

        concept, ok = QtWidgets.QInputDialog.getItem(
            self._parent,
            "Change concept",
            "Concept:",
            kb_concepts,
            editable=False,
        )
        if not ok:
            return None

        controller = self._controller()
        if controller is None:
            return None

        self._image_mosaic.select(rect_widget)
        self._pending_action = "label"
        controller.label_selected(
            [rect_widget.association],
            concept,
            rect_widget.association.part,
            self._settings.username.value,
        )
        return concept

    def change_part_from_box(
        self,
        rect_widget: RectWidget,
        current_part: str,
    ) -> str | None:
        _ = current_part
        if not self._ensure_annotation_ready():
            return None

        kb_service = self._kb_service()
        if kb_service is None:
            QtWidgets.QMessageBox.critical(
                self._parent,
                "Not Ready",
                "Knowledge base service is not initialized.",
            )
            return None
        kb_parts = list(kb_service.get_parts())

        part, ok = QtWidgets.QInputDialog.getItem(
            self._parent,
            "Change part",
            "Part:",
            kb_parts,
            editable=False,
        )
        if not ok:
            return None

        controller = self._controller()
        if controller is None:
            return None

        self._image_mosaic.select(rect_widget)
        self._pending_action = "label"
        controller.label_selected(
            [rect_widget.association],
            rect_widget.association.concept,
            part,
            self._settings.username.value,
        )
        return part

    def delete_from_tile(self, rect_widget: RectWidget) -> None:
        """A tile's right-click "Delete...": the whole selection if that tile
        is part of it (as in a file browser), otherwise just that tile."""
        if not self._ensure_annotation_ready() or self._busy():
            return
        selected = self._image_mosaic.get_selected()
        if rect_widget in selected:
            targets = list(selected)
        else:
            self._image_mosaic.select(rect_widget)
            targets = [rect_widget]
        count = len(targets)
        what = "this localization" if count == 1 else f"{count} localizations"
        confirm = QtWidgets.QMessageBox.question(
            self._parent,
            "Confirm Deletion",
            f"Delete {what}?\nThis operation cannot be undone.",
            defaultButton=QtWidgets.QMessageBox.StandardButton.No,
        )
        if confirm != QtWidgets.QMessageBox.StandardButton.Yes:
            return
        self._dispatch_delete(targets)

    def delete_from_box(self, rect_widget: RectWidget) -> None:
        if not self._ensure_annotation_ready() or self._busy():
            return
        self._image_mosaic.select(rect_widget)
        confirm = QtWidgets.QMessageBox.question(
            self._parent,
            "Confirm Deletion",
            "Delete this localization?\nThis operation cannot be undone.",
            defaultButton=QtWidgets.QMessageBox.StandardButton.No,
        )
        if confirm != QtWidgets.QMessageBox.StandardButton.Yes:
            return
        self._dispatch_delete([rect_widget])

    def label_single_from_tile(
        self,
        rect_widget: RectWidget,
        concept: str,
        part: str,
    ) -> None:
        if not self._ensure_annotation_ready() or self._busy():
            return
        controller = self._controller()
        if controller is None:
            return
        self._image_mosaic.select(rect_widget)
        self._pending_action = "label"
        controller.label_selected(
            [rect_widget.association],
            concept,
            part,
            self._settings.username.value,
        )

    def verify_single_from_tile(self, rect_widget: RectWidget) -> None:
        if not self._ensure_annotation_ready() or self._busy():
            return
        controller = self._controller()
        if controller is None:
            return
        self._image_mosaic.select(rect_widget)
        self._pending_action = "verify"
        controller.verify_selected(
            [rect_widget.association],
            True,
            self._settings.username.value,
        )

    def mark_training_single_from_tile(self, rect_widget: RectWidget) -> None:
        if not self._ensure_annotation_ready() or self._busy():
            return
        controller = self._controller()
        if controller is None:
            return
        self._image_mosaic.select(rect_widget)
        self._pending_action = "mark_training"
        controller.mark_training_selected(
            [rect_widget.association],
            True,
            self._settings.username.value,
        )
