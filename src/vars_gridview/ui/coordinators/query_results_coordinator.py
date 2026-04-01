"""Coordinator for composing query results into mosaic/detail state."""

from __future__ import annotations

from typing import Callable

from PyQt6 import QtWidgets

from vars_gridview.lib.annotation.box_handler import BoxHandler
from vars_gridview.lib.config.settings import AppSettings
from vars_gridview.lib.runtime.log import LOGGER
from vars_gridview.lib.sorting.sort_methods import RecordedTimestampSort
from vars_gridview.ui.mosaic.image_mosaic import ImageMosaic
from vars_gridview.ui.mosaic.rect_widget import RectWidget


class QueryResultsCoordinator:
    """Own result application from query payloads to view state."""

    def __init__(
        self,
        *,
        parent: QtWidgets.QWidget,
        image_mosaic: ImageMosaic,
        sort_dialog_getter: Callable[[], object],
        roi_detail_graphics_view,
        settings: AppSettings,
        kb_service_getter: Callable[[], object | None],
        annotation_service_getter: Callable[[], object | None],
        change_concept_callback: Callable[[RectWidget, str], str | None],
        change_part_callback: Callable[[RectWidget, str], str | None],
        delete_callback: Callable[[RectWidget], None],
    ) -> None:
        self._parent = parent
        self._image_mosaic = image_mosaic
        self._sort_dialog_getter = sort_dialog_getter
        self._roi_detail_graphics_view = roi_detail_graphics_view
        self._settings = settings
        self._kb_service_getter = kb_service_getter
        self._annotation_service_getter = annotation_service_getter
        self._change_concept_callback = change_concept_callback
        self._change_part_callback = change_part_callback
        self._delete_callback = delete_callback

    def apply_query_results(
        self,
        *,
        query_headers: list[str],
        query_rows: list[list[str]],
        hide_labeled: bool,
        hide_unlabeled: bool,
        hide_training: bool,
        hide_nontraining: bool,
    ) -> BoxHandler | None:
        self._image_mosaic.hide_labeled = hide_labeled
        self._image_mosaic.hide_unlabeled = hide_unlabeled
        self._image_mosaic.hide_training = hide_training
        self._image_mosaic.hide_nontraining = hide_nontraining

        self._image_mosaic.populate(query_headers, query_rows)

        sort_dialog = self._sort_dialog_getter()
        sort_dialog.clear()
        self._image_mosaic.sort_rect_widgets(RecordedTimestampSort)
        self._image_mosaic.render_mosaic()

        kb_service = self._kb_service_getter()
        if kb_service is None:
            LOGGER.error(
                "Could not get KB concepts: Knowledge base service is unavailable"
            )
            return None

        try:
            kb_concepts = list(kb_service.get_concepts().keys())
        except Exception as exc:  # noqa: BLE001
            LOGGER.error(f"Could not get KB concepts: {exc}")
            return None

        annotation_service = self._annotation_service_getter()
        return BoxHandler(
            self._roi_detail_graphics_view,
            self._image_mosaic,
            all_labels=kb_concepts,
            settings=self._settings,
            push_changes_callback=(
                annotation_service.push_changes
                if annotation_service is not None
                else None
            ),
            change_concept_callback=self._change_concept_callback,
            change_part_callback=self._change_part_callback,
            delete_callback=self._delete_callback,
        )


__all__ = ["QueryResultsCoordinator"]
