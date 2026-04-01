from vars_gridview.controllers.query_controller import QueryController
from vars_gridview.lib.m3.query import QueryConstraint


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
