from types import SimpleNamespace

from vars_gridview.ui.coordinators.detail_pane_coordinator import DetailPaneCoordinator


class _FakeBoxHandler:
    def __init__(self, result: bool):
        self.result = result
        self.calls = []

    def retarget_annotations_for_same_source(self, rect):
        self.calls.append(rect)
        return self.result


def test_update_overlays_for_same_source_uses_box_handler() -> None:
    rect = SimpleNamespace(localization_index=1)
    box_handler = _FakeBoxHandler(True)

    coordinator = DetailPaneCoordinator(
        box_handler_getter=lambda: box_handler,
        selected_rect_getter=lambda: None,
    )

    assert coordinator.update_overlays_for_same_source(rect) is True
    assert box_handler.calls == [rect]


def test_update_overlays_for_same_source_without_box_handler() -> None:
    rect = SimpleNamespace(localization_index=1)

    coordinator = DetailPaneCoordinator(
        box_handler_getter=lambda: None,
        selected_rect_getter=lambda: None,
    )

    assert coordinator.update_overlays_for_same_source(rect) is False
