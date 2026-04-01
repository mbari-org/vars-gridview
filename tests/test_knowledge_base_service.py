from __future__ import annotations

from vars_gridview.services.knowledge_base_service import KnowledgeBaseService


class _FakeResponse:
    def __init__(self, payload, status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code
        self.raise_calls = 0

    def raise_for_status(self) -> None:
        self.raise_calls += 1

    def json(self):
        return self._payload


class _FakeKbClient:
    def __init__(self) -> None:
        self.concepts_calls = 0
        self.concept_calls = []
        self.parts_calls = 0
        self.phylogeny_calls = []

    def get_concepts(self):
        self.concepts_calls += 1
        return _FakeResponse(["A", "B"])

    def get_concept(self, concept: str):
        self.concept_calls.append(concept)
        return _FakeResponse({"name": f"Common {concept}"})

    def get_parts(self):
        self.parts_calls += 1
        return _FakeResponse([{"name": "fin"}, {"name": "tail"}])

    def get_phylogeny_taxa(self, concept: str):
        self.phylogeny_calls.append(concept)
        if concept == "missing":
            return _FakeResponse([], status_code=404)
        return _FakeResponse([{"name": concept}, {"name": f"{concept}-child"}])


class _FakeVampireSquidClient:
    def __init__(self) -> None:
        self.calls = 0

    def get_video_sequence_names(self):
        self.calls += 1
        return _FakeResponse(["seq-a", "seq-b"])


def test_get_concepts_and_concept_name_use_cache() -> None:
    kb = _FakeKbClient()
    vs = _FakeVampireSquidClient()
    service = KnowledgeBaseService(kb, vs)

    concepts_1 = service.get_concepts()
    concepts_2 = service.get_concepts()

    assert concepts_1 is concepts_2
    assert kb.concepts_calls == 1

    assert service.get_concept_name("A") == "Common A"
    assert service.get_concept_name("A") == "Common A"
    assert kb.concept_calls == ["A"]


def test_get_parts_and_video_sequence_names_cached() -> None:
    kb = _FakeKbClient()
    vs = _FakeVampireSquidClient()
    service = KnowledgeBaseService(kb, vs)

    assert service.get_parts() == ["fin", "tail"]
    assert service.get_parts() == ["fin", "tail"]
    assert kb.parts_calls == 1

    assert service.get_video_sequence_names() == ["seq-a", "seq-b"]
    assert service.get_video_sequence_names() == ["seq-a", "seq-b"]
    assert vs.calls == 1


def test_get_descendants_handles_404_as_empty_list() -> None:
    kb = _FakeKbClient()
    service = KnowledgeBaseService(kb, _FakeVampireSquidClient())

    assert service.get_descendants("missing") == []
    assert service.get_descendants("root") == ["root", "root-child"]


def test_invalidate_clears_cached_state() -> None:
    kb = _FakeKbClient()
    vs = _FakeVampireSquidClient()
    service = KnowledgeBaseService(kb, vs)

    service.get_concepts()
    service.get_parts()
    service.get_video_sequence_names()
    service.get_concept_name("A")

    service.invalidate()

    service.get_concepts()
    service.get_parts()
    service.get_video_sequence_names()
    service.get_concept_name("A")

    assert kb.concepts_calls == 2
    assert kb.parts_calls == 2
    assert vs.calls == 2
    assert kb.concept_calls == ["A", "A"]
