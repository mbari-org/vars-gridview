from __future__ import annotations

from uuid import UUID

from vars_gridview.services.annotation_service import AnnotationService


class _FakeResponse:
    def raise_for_status(self) -> None:
        return None

    def json(self):
        return {}


class _FakeAnnosaurusClient:
    def __init__(self) -> None:
        self.updated_observations = []
        self.updated_associations = []

    def update_observation(self, observation_uuid: str, data: dict):
        self.updated_observations.append((observation_uuid, data))
        return _FakeResponse()

    def update_association(self, association_uuid: str, data: dict):
        self.updated_associations.append((association_uuid, data))
        return _FakeResponse()

    def delete_association(self, _association_uuid: str):
        return _FakeResponse()

    def delete_observation(self, _observation_uuid: str):
        return _FakeResponse()

    def get_observation(self, _observation_uuid: str):
        class _ObsResponse(_FakeResponse):
            def json(self_inner):
                return {
                    "associations": [
                        {
                            "uuid": "11111111-1111-1111-1111-111111111111",
                            "link_name": "bounding box",
                        },
                        {
                            "uuid": "22222222-2222-2222-2222-222222222222",
                            "link_name": "comment",
                        },
                    ]
                }

        return _ObsResponse()


class _FakeObservation:
    def __init__(self, uuid: str) -> None:
        self.uuid = UUID(uuid)


class _FakeAssociation:
    def __init__(self) -> None:
        self.uuid = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
        self.observation = _FakeObservation("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
        self.concept = "animal"
        self.part = "self"
        self.data = {"x": 1, "y": 2, "width": 3, "height": 4}
        self.deleted = False
        self._dirty_concept = False
        self._dirty_part = False
        self._dirty_box = False


def test_push_changes_updates_only_dirty_fields() -> None:
    client = _FakeAnnosaurusClient()
    service = AnnotationService(client, default_observer="default")
    assoc = _FakeAssociation()
    assoc._dirty_concept = True
    assoc._dirty_part = True
    assoc._dirty_box = True

    service.push_changes(assoc)

    assert client.updated_observations == [
        (
            "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
            {"concept": "animal", "observer": "default"},
        )
    ]
    assert len(client.updated_associations) == 2
    assert assoc._dirty_concept is False
    assert assoc._dirty_part is False
    assert assoc._dirty_box is False


def test_push_changes_skips_deleted_association() -> None:
    client = _FakeAnnosaurusClient()
    service = AnnotationService(client, default_observer="default")
    assoc = _FakeAssociation()
    assoc.deleted = True
    assoc._dirty_box = True

    service.push_changes(assoc)

    assert client.updated_observations == []
    assert client.updated_associations == []


def test_get_observation_bounding_box_association_uuids_filters_by_link_name() -> None:
    client = _FakeAnnosaurusClient()
    service = AnnotationService(client, default_observer="default")

    uuids = service.get_observation_bounding_box_association_uuids(
        UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")
    )

    assert uuids == {UUID("11111111-1111-1111-1111-111111111111")}


def test_push_changes_uses_observer_override() -> None:
    client = _FakeAnnosaurusClient()
    service = AnnotationService(client, default_observer="default")
    assoc = _FakeAssociation()
    assoc._dirty_concept = True

    service.push_changes(assoc, observer="override-user")

    assert client.updated_observations == [
        (
            "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
            {"concept": "animal", "observer": "override-user"},
        )
    ]


def test_push_changes_box_only_updates_link_value() -> None:
    client = _FakeAnnosaurusClient()
    service = AnnotationService(client, default_observer="default")
    assoc = _FakeAssociation()
    assoc._dirty_box = True

    service.push_changes(assoc)

    assert client.updated_observations == []
    assert len(client.updated_associations) == 1
    association_uuid, payload = client.updated_associations[0]
    assert association_uuid == "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    assert "link_value" in payload
