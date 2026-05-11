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
from vars_gridview.ui.coordinators.shutdown_save_coordinator import (
    ShutdownSaveCoordinator,
)
from vars_gridview.ui.coordinators.query_presentation_coordinator import (
    QueryPresentationCoordinator,
)
from vars_gridview.ui.coordinators.dirty_association_save_coordinator import (
    DirtyAssociationSaveCoordinator,
)
from vars_gridview.ui.coordinators.mosaic_roi_loading_coordinator import (
    MosaicRoiLoadingCoordinator,
)
from vars_gridview.ui.coordinators.mosaic_similarity_coordinator import (
    MosaicSimilarityCoordinator,
)
from vars_gridview.ui.coordinators.mosaic_embedding_coordinator import (
    MosaicEmbeddingCoordinator,
)
from vars_gridview.ui.coordinators.mosaic_tile_action_coordinator import (
    MosaicTileActionCoordinator,
)

__all__ = [
    "AnnotationActionCoordinator",
    "AnnotationOperationPresenter",
    "DetailPaneCoordinator",
    "DirtyAssociationSaveCoordinator",
    "MainWindowMenuCoordinator",
    "MosaicRoiLoadingCoordinator",
    "MosaicEmbeddingCoordinator",
    "MosaicSimilarityCoordinator",
    "MosaicTileActionCoordinator",
    "QueryPresentationCoordinator",
    "ShutdownSaveCoordinator",
    "VideoNavigationCoordinator",
]
