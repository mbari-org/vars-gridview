from vars_gridview.controllers.annotation_controller import AnnotationController
from uuid import UUID


class _FakeObservation:
    def __init__(self, uuid: str):
        self.uuid = UUID(uuid)


class _FakeAssoc:
    def __init__(
        self, uuid: str, observation_uuid: str = "00000000-0000-0000-0000-000000000000"
    ):
        self.uuid = (
            UUID(f"00000000-0000-0000-0000-{uuid:0>12}") if uuid.isdigit() else uuid
        )
        self.observation = _FakeObservation(observation_uuid)
        self.deleted = False
        self.verify_calls = 0
        self.unverify_calls = 0
        self.mark_calls = 0
        self.unmark_calls = 0
        self.set_verified_concept_calls = []

    def set_verified_concept(self, concept, part, observer):
        self.set_verified_concept_calls.append((concept, part, observer))

    def verify(self, _observer):
        self.verify_calls += 1

    def unverify(self):
        self.unverify_calls += 1

    def mark_for_training(self):
        self.mark_calls += 1

    def unmark_for_training(self):
        self.unmark_calls += 1


class _FakeAnnotationService:
    def __init__(self, fail_uuid=None):
        self.observer = "tester"
        self.fail_uuid = fail_uuid
        self.pushed = []
        self.deleted = []
        self.deleted_observations = []
        self.observation_assoc_map = {}

    def push_changes(self, assoc, _observer=None):
        if assoc.uuid == self.fail_uuid:
            raise RuntimeError("boom")
        self.pushed.append(assoc.uuid)

    def delete_association(self, assoc):
        if assoc.uuid == self.fail_uuid:
            raise RuntimeError("boom")
        self.deleted.append(assoc.uuid)

    def delete_observation(self, observation_uuid):
        self.deleted_observations.append(observation_uuid)

    def get_observation_bounding_box_association_uuids(self, observation_uuid):
        return self.observation_assoc_map.get(observation_uuid, set())


class _FakeKB:
    def get_concept_name(self, concept):
        return concept


def _controller(annotation_service):
    return AnnotationController(annotation_service, _FakeKB())  # type: ignore[arg-type]


def test_apply_labels_collects_failures():
    service = _FakeAnnotationService(
        fail_uuid=UUID("00000000-0000-0000-0000-000000000002")
    )
    ctrl = _controller(service)
    a1 = _FakeAssoc("1")
    a2 = _FakeAssoc("2")

    try:
        ctrl._apply_labels([a1, a2], "A", "self", "observer")
        assert False, "Expected RuntimeError"
    except RuntimeError as exc:
        assert "Failed to label 1 of 2" in str(exc)
        assert "2: boom" in str(exc)

    assert service.pushed == [UUID("00000000-0000-0000-0000-000000000001")]
    assert a1.set_verified_concept_calls == [("A", "self", "observer")]
    assert a2.set_verified_concept_calls == [("A", "self", "observer")]


def test_apply_verified_and_training_paths():
    service = _FakeAnnotationService()
    ctrl = _controller(service)
    a = _FakeAssoc("1")

    ctrl._apply_verified([a], True, "observer")
    ctrl._apply_verified([a], False, "observer")
    ctrl._apply_training([a], True, "observer")
    ctrl._apply_training([a], False, "observer")

    assert a.verify_calls == 1
    assert a.unverify_calls == 1
    assert a.mark_calls == 1
    assert a.unmark_calls == 1


def test_apply_delete_collects_failures():
    failing_uuid = UUID("00000000-0000-0000-0000-000000000002")
    service = _FakeAnnotationService(fail_uuid=failing_uuid)
    ctrl = _controller(service)
    a1 = _FakeAssoc("1")
    a2 = _FakeAssoc("2")

    try:
        ctrl._apply_delete([a1, a2])
        assert False, "Expected RuntimeError"
    except RuntimeError as exc:
        assert "Failed to delete 1 of 2" in str(exc)

    assert service.deleted == [UUID("00000000-0000-0000-0000-000000000001")]


def test_plan_delete_detects_dangling_observations():
    service = _FakeAnnotationService()
    ctrl = _controller(service)
    obs_uuid = UUID("11111111-1111-1111-1111-111111111111")
    assoc_uuid = UUID("00000000-0000-0000-0000-000000000001")
    service.observation_assoc_map[obs_uuid] = {assoc_uuid}

    assoc = _FakeAssoc("1", observation_uuid=str(obs_uuid))
    plan = ctrl.plan_delete([assoc])

    assert plan.dangling_count == 1
    assert plan.dangling_observation_uuids == {obs_uuid}


def test_apply_delete_can_delete_dangling_observations():
    service = _FakeAnnotationService()
    ctrl = _controller(service)
    obs_uuid = UUID("11111111-1111-1111-1111-111111111111")

    a1 = _FakeAssoc("1", observation_uuid=str(obs_uuid))
    a2 = _FakeAssoc("2", observation_uuid=str(obs_uuid))

    ctrl._apply_delete([a1, a2], {obs_uuid})

    assert service.deleted_observations == [obs_uuid]
    assert service.deleted == []
    assert a1.deleted is True
    assert a2.deleted is True
