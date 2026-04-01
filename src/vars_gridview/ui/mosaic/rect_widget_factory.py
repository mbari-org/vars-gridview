"""Factory for creating mosaic RectWidget UI instances from ROI specs."""

from __future__ import annotations

from typing import Callable

from vars_gridview.lib.config.constants import get_settings
from vars_gridview.lib.config.settings import AppSettings
from vars_gridview.services.roi_loader import RoiWidgetSpec
from vars_gridview.ui.mosaic.rect_widget import RectWidget


class RectWidgetFactory:
    """Build ``RectWidget`` instances from service-provided widget specs."""

    def __init__(
        self,
        *,
        rect_clicked_slot: Callable,
        similarity_sort_slot: Callable,
        rect_label_slot: Callable,
        rect_verify_slot: Callable,
        rect_mark_training_slot: Callable,
        settings: AppSettings | None = None,
    ) -> None:
        self._rect_clicked_slot = rect_clicked_slot
        self._similarity_sort_slot = similarity_sort_slot
        self._rect_label_slot = rect_label_slot
        self._rect_verify_slot = rect_verify_slot
        self._rect_mark_training_slot = rect_mark_training_slot
        self._settings = settings or get_settings()

    def create(
        self,
        spec: RoiWidgetSpec,
        *,
        embedding_model,
        roi_service,
    ) -> RectWidget:
        """Create one ``RectWidget`` for the given ROI spec."""
        return RectWidget(
            spec.associations,
            spec.source_url,
            spec.is_image,
            spec.ancillary_data,
            spec.video_data,
            spec.association_index,
            self._rect_clicked_slot,
            self._similarity_sort_slot,
            self._rect_label_slot,
            self._rect_verify_slot,
            self._rect_mark_training_slot,
            text_label=spec.associations[spec.association_index].text_label,
            embedding_model=embedding_model,
            roi_service=roi_service,
            scale_x=spec.scale_x,
            scale_y=spec.scale_y,
            video_url=spec.video_url,
            elapsed_time_millis=spec.elapsed_time_millis,
            preload_roi=False,
            settings=self._settings,
        )


__all__ = ["RectWidgetFactory"]
