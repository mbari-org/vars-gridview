"""Coordinator for mosaic rect selection and detail-pane interaction flow."""

from __future__ import annotations

from typing import Callable, Optional, TYPE_CHECKING

from PyQt6 import QtCore, QtGui, QtWidgets

from vars_gridview.lib.runtime.log import LOGGER
from vars_gridview.lib.runtime.runnables import Worker

if TYPE_CHECKING:
    from vars_gridview.lib.annotation.box_handler import BoxHandler
    from vars_gridview.ui.coordinators.detail_pane_coordinator import (
        DetailPaneCoordinator,
    )
    from vars_gridview.ui.mosaic.image_mosaic import ImageMosaic
    from vars_gridview.ui.mosaic.rect_widget import RectWidget


class RectInteractionCoordinator(QtCore.QObject):
    """Own rect click behavior, selection updates, and detail pane metadata updates."""

    def __init__(
        self,
        *,
        parent: QtCore.QObject,
        dialog_parent: QtWidgets.QWidget,
        image_mosaic: ImageMosaic,
        detail_pane: DetailPaneCoordinator,
        roi_detail_graphics_view: QtWidgets.QWidget,
        bounding_box_info_tree,
        image_info_tree,
        loaded_getter: Callable[[], bool],
        box_handler_getter: Callable[[], BoxHandler | None],
        last_selected_getter: Callable[[], RectWidget | None],
        last_selected_setter: Callable[[RectWidget | None], None],
        save_dirty_associations_worker: Callable[[list], set],
    ) -> None:
        super().__init__(parent)
        self._dialog_parent = dialog_parent
        self._image_mosaic = image_mosaic
        self._detail_pane = detail_pane
        self._roi_detail_graphics_view = roi_detail_graphics_view
        self._bounding_box_info_tree = bounding_box_info_tree
        self._image_info_tree = image_info_tree
        self._loaded_getter = loaded_getter
        self._box_handler_getter = box_handler_getter
        self._last_selected_getter = last_selected_getter
        self._last_selected_setter = last_selected_setter
        self._save_dirty_associations_worker = save_dirty_associations_worker

        self._pre_click_save_in_progress = False
        self._pending_rect_clicks: list[tuple[RectWidget, bool, bool]] = []

    def clear_detail_panels(self) -> None:
        """Clear both detail metadata panels."""
        self._bounding_box_info_tree.clear()
        self._image_info_tree.clear()

    def handle_rect_clicked(
        self,
        rect: RectWidget,
        event: Optional[QtGui.QMouseEvent],
    ) -> None:
        """Persist dirty boxes off-thread before applying click selection state."""
        if not self._loaded_getter():
            return
        self._save_dirty_boxes_then_handle_click(rect, event)

    @staticmethod
    def _selection_modifiers(event: object | None) -> tuple[bool, bool]:
        """Return ``(ctrl, shift)`` modifier state for a click event."""
        if event is None:
            return False, False
        try:
            modifiers = event.modifiers()  # type: ignore[call-arg]
            ctrl = bool(modifiers & QtCore.Qt.KeyboardModifier.ControlModifier)
            shift = bool(modifiers & QtCore.Qt.KeyboardModifier.ShiftModifier)
        except Exception:
            # Some Qt event wrappers can become invalid after async boundaries.
            return False, False
        return ctrl, shift

    def _save_dirty_boxes_then_handle_click(
        self,
        rect: RectWidget,
        event: Optional[QtGui.QMouseEvent],
    ) -> None:
        ctrl, shift = self._selection_modifiers(event)

        box_handler = self._box_handler_getter()
        if box_handler is None:
            self._apply_rect_click(rect, ctrl=ctrl, shift=shift)
            return

        self._pending_rect_clicks.append((rect, ctrl, shift))
        if self._pre_click_save_in_progress:
            return

        dirty_associations = box_handler.get_dirty_associations()
        if not dirty_associations:
            pending = self._dequeue_latest_click()
            if pending is not None:
                self._apply_rect_click(pending[0], ctrl=pending[1], shift=pending[2])
            return

        self._pre_click_save_in_progress = True
        self._roi_detail_graphics_view.setEnabled(False)

        worker = Worker(self._save_dirty_associations_worker, dirty_associations)
        worker.signals.result.connect(self._on_pre_click_save_ready)
        worker.signals.error.connect(self._on_pre_click_save_error)
        worker.signals.finished.connect(self._on_pre_click_save_finished)
        pool = QtCore.QThreadPool.globalInstance()
        if pool is None:
            self._on_pre_click_save_error(
                (RuntimeError, RuntimeError("No thread pool"), "")
            )
            self._on_pre_click_save_finished()
            return
        pool.start(worker)

    @QtCore.pyqtSlot(object)
    def _on_pre_click_save_ready(self, saved_association_uuids: object) -> None:
        box_handler = self._box_handler_getter()
        if box_handler is not None and isinstance(saved_association_uuids, set):
            box_handler.clear_dirty_for(saved_association_uuids)

        pending = self._dequeue_latest_click()
        if pending is not None:
            self._apply_rect_click(pending[0], ctrl=pending[1], shift=pending[2])

    @QtCore.pyqtSlot(tuple)
    def _on_pre_click_save_error(self, err: tuple) -> None:
        self._pending_rect_clicks.clear()
        message = str(err[1]) if len(err) > 1 else "Unknown error"
        summary = "Could not save localizations before selection change."
        details = message

        marker = "Failed to save one or more localizations before selection change:"
        if marker in message:
            lines = [line.strip() for line in message.splitlines() if line.strip()]
            failure_lines = [line for line in lines if ":" in line and line != marker]
            if failure_lines:
                preview_count = min(8, len(failure_lines))
                preview = "\n".join(failure_lines[:preview_count])
                extra = len(failure_lines) - preview_count
                if extra > 0:
                    preview = f"{preview}\n... and {extra} more"
                summary = f"Failed to save {len(failure_lines)} localization(s)."
                details = preview

        LOGGER.error("Could not save localizations: %s", message)
        QtWidgets.QMessageBox.critical(
            self._dialog_parent,
            "Error",
            f"{summary}\n\n{details}",
        )

    def _dequeue_latest_click(self) -> Optional[tuple[RectWidget, bool, bool]]:
        if not self._pending_rect_clicks:
            return None
        latest = self._pending_rect_clicks[-1]
        self._pending_rect_clicks.clear()
        return latest

    @QtCore.pyqtSlot()
    def _on_pre_click_save_finished(self) -> None:
        self._pre_click_save_in_progress = False
        self._roi_detail_graphics_view.setEnabled(True)

    def _update_mosaic_selection(
        self,
        rect: RectWidget,
        ctrl: bool,
        shift: bool,
    ) -> None:
        """Apply ctrl/shift selection behavior in the mosaic view."""
        anchor = self._image_mosaic.selection_anchor
        if shift and anchor is not None:
            # Shift+Click: extend range from anchor; Ctrl+Shift adds to existing selection.
            self._image_mosaic.select_range(anchor, rect, add=ctrl)
        elif ctrl and rect.is_selected:
            self._image_mosaic.deselect(rect)
        else:
            self._image_mosaic.select(rect, clear=not ctrl)

    def _clear_last_detail_selection(
        self,
        *,
        clear_detail_overlays: bool = True,
    ) -> None:
        """Remove highlight and detail overlays from the prior selected tile."""
        last_selected_rect = self._last_selected_getter()
        if last_selected_rect is None:
            return

        box_handler = self._box_handler_getter()
        if clear_detail_overlays and box_handler is not None:
            box_handler.clear()

        last_selected_rect.is_last_selected = False
        last_selected_rect.update()

    def _detail_view_minimized(self) -> bool:
        """Return True when the detail view cannot render content visibly."""
        return (
            self._roi_detail_graphics_view.width() == 0
            or self._roi_detail_graphics_view.height() == 0
        )

    def _populate_detail_metadata(self, rect: RectWidget) -> None:
        """Refresh detail info panels for the selected localization."""
        self._bounding_box_info_tree.set_data(rect.association.data)

        ancillary_data = rect.ancillary_data.copy()
        annotation_datetime = rect.annotation_datetime()
        if annotation_datetime is not None:
            ancillary_data["derived_timestamp"] = annotation_datetime.strftime(
                "%Y-%m-%d %H:%M:%S"
            )
        ancillary_data["observation_observer"] = rect.association.observation.observer
        ancillary_data["observation_group"] = rect.association.observation.group
        ancillary_data["imaged_moment_uuid"] = rect.imaged_moment_uuid
        ancillary_data["observation_uuid"] = rect.observation_uuid
        ancillary_data["association_uuid"] = rect.association_uuid

        if rect.association.image_reference_uuid:
            ancillary_data["image_reference_uuid"] = (
                rect.association.image_reference_uuid
            )

        self._image_info_tree.set_data(ancillary_data)

    def _apply_rect_click(
        self,
        rect: RectWidget,
        event: Optional[QtGui.QMouseEvent] = None,
        ctrl: Optional[bool] = None,
        shift: Optional[bool] = None,
    ) -> None:
        if not self._loaded_getter():
            return

        if ctrl is None or shift is None:
            ctrl, shift = self._selection_modifiers(event)

        previous_rect = self._last_selected_getter()
        same_image = False
        if previous_rect is not None:
            same_image = self._detail_pane.rect_source_key(
                rect
            ) == self._detail_pane.rect_source_key(previous_rect)

        self._update_mosaic_selection(rect, ctrl, shift)
        self._clear_last_detail_selection(clear_detail_overlays=not same_image)

        image_view_minimized = self._detail_view_minimized()
        needs_autorange = not (same_image or image_view_minimized)

        rect.is_last_selected = True
        rect.update()
        self._last_selected_setter(rect)

        if not image_view_minimized:
            reused_overlays = False
            if same_image:
                reused_overlays = self._detail_pane.update_overlays_for_same_source(
                    rect
                )

            if not reused_overlays:
                box_handler = self._box_handler_getter()
                if same_image and box_handler is not None:
                    # Reuse failed (e.g. box count changed); force a clean redraw.
                    box_handler.clear()
                self._detail_pane.show_rect_in_detail_async(rect, needs_autorange)

        self._populate_detail_metadata(rect)


__all__ = ["RectInteractionCoordinator"]
