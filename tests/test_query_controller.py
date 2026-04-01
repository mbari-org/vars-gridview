from vars_gridview.controllers.query_controller import QueryController
from vars_gridview.lib.m3.query import QueryConstraint


def _build_request_from_execute(ctrl: QueryController):
    captured = {}

    def _capture(request):
        captured["request"] = request

    ctrl._dispatch = _capture  # type: ignore[method-assign]
    ctrl.execute([QueryConstraint("observer", equals="bob")], limit=10, offset=0)
    return captured["request"]


def test_execute_builds_query_request_with_required_fields():
    ctrl = QueryController()
    captured = {}

    def _capture(request):
        captured["request"] = request

    ctrl._dispatch = _capture  # type: ignore[method-assign]

    ctrl.execute([QueryConstraint("concept", equals="A")], limit=25, offset=50)

    req = captured["request"]
    assert req.limit == 25
    assert req.offset == 50
    assert req.order_by == ["index_recorded_timestamp"]
    assert req.select is not None
    assert "association_uuid" in req.select
    assert req.where is not None
    assert any(
        c.column == "link_name" and c.equals == "bounding box" for c in req.where
    )
    assert any(c.column == "concept" and c.equals == "A" for c in req.where)


def test_paging_carries_previous_constraints():
    ctrl = QueryController()
    requests = []

    def _capture(request):
        requests.append(request)

    ctrl._dispatch = _capture  # type: ignore[method-assign]
    ctrl.execute([QueryConstraint("observer", equals="bob")], limit=10, offset=0)

    first = requests[-1]
    ctrl._last_request = first
    ctrl._total_rows = 35

    ctrl.next_page()
    second = requests[-1]
    assert second.offset == 10
    assert second.where == first.where
    assert second.select == first.select
    ctrl._last_request = second

    ctrl.previous_page()
    third = requests[-1]
    assert third.offset == 0
    assert third.where == first.where
    assert third.select == first.select


def test_on_count_result_ignores_stale_generation() -> None:
    ctrl = QueryController()
    request = _build_request_from_execute(ctrl)
    progress_calls = []
    ctrl.query_progress.connect(
        lambda message, step, total: progress_calls.append((message, step, total))
    )

    ctrl._request_generation = 2
    ctrl._on_count_result((request, 100, 1))

    assert progress_calls == []


def test_on_download_result_ignores_stale_generation() -> None:
    ctrl = QueryController()
    request = _build_request_from_execute(ctrl)
    progress_calls = []
    ctrl.query_progress.connect(
        lambda message, step, total: progress_calls.append((message, step, total))
    )

    ctrl._request_generation = 5
    ctrl._on_download_result((request, 100, 4, "h\trow"))

    assert progress_calls == []


def test_on_result_ignores_stale_generation() -> None:
    ctrl = QueryController()
    request = _build_request_from_execute(ctrl)
    ready_payloads = []
    ctrl.results_ready.connect(
        lambda headers, rows, page, total_pages, total_rows: ready_payloads.append(
            (headers, rows, page, total_pages, total_rows)
        )
    )

    ctrl._request_generation = 10
    ctrl._on_result((request, 100, 9, ["a"], [["b"]]))

    assert ready_payloads == []
    assert ctrl.has_results is False
