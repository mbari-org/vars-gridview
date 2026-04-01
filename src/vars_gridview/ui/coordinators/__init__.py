"""UI coordinators for MainWindow behaviors and flows."""

from vars_gridview.ui.coordinators.annotation_action_coordinator import (
    AnnotationActionCoordinator,
)
from vars_gridview.ui.coordinators.annotation_operation_presenter import (
    AnnotationOperationPresenter,
)
from vars_gridview.ui.coordinators.detail_pane_coordinator import DetailPaneCoordinator
from vars_gridview.ui.coordinators.main_window_menu_coordinator import (
    MainWindowMenuCoordinator,
)
from vars_gridview.ui.coordinators.video_navigation_coordinator import (
    VideoNavigationCoordinator,
)

__all__ = [
    "AnnotationActionCoordinator",
    "AnnotationOperationPresenter",
    "DetailPaneCoordinator",
    "MainWindowMenuCoordinator",
    "VideoNavigationCoordinator",
]
