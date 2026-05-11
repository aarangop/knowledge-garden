"""Tests for abstract interfaces — contract: specifications/01_foundation/contract.md, section 3."""
import pytest

from knowledge_garden.services.embedder import EmbeddingService
from knowledge_garden.services.graph_store import GraphStore


class TestEmbeddingService:
    """Contract section 3.1 — EmbeddingService ABC."""

    @pytest.mark.unit
    def test_embedding_service_is_abstract(self):
        """Contract: Instantiating EmbeddingService() directly raises TypeError."""
        with pytest.raises(TypeError):
            EmbeddingService()

    @pytest.mark.unit
    def test_embedding_service_requires_embed(self):
        """Contract: Subclass that omits embed() cannot be instantiated — raises TypeError."""

        class MissingEmbed(EmbeddingService):
            def dimension(self) -> int:
                return 768

        with pytest.raises(TypeError):
            MissingEmbed()

    @pytest.mark.unit
    def test_embedding_service_requires_dimension(self):
        """Contract: Subclass that omits dimension() cannot be instantiated — raises TypeError."""

        class MissingDimension(EmbeddingService):
            async def embed(self, texts: list[str]) -> list[list[float]]:
                return []

        with pytest.raises(TypeError):
            MissingDimension()


class TestGraphStore:
    """Contract section 3.2 — GraphStore ABC."""

    @pytest.mark.unit
    def test_graph_store_is_abstract(self):
        """Contract: Instantiating GraphStore() directly raises TypeError."""
        with pytest.raises(TypeError):
            GraphStore()

    @pytest.mark.unit
    def test_graph_store_requires_all_methods(self):
        """Contract: Subclass missing any one abstract method raises TypeError on instantiation.

        GraphStore has 12 abstract methods. This subclass implements all except
        get_chunks_for_note, which is sufficient to trigger TypeError.
        """

        class IncompleteGraphStore(GraphStore):
            async def initialize(self) -> None:
                pass

            async def close(self) -> None:
                pass

            async def upsert_note(self, note) -> None:
                pass

            async def upsert_chunk(self, chunk) -> None:
                pass

            async def create_link(self, from_note_id, to_note_id, rel_type: str) -> None:
                pass

            async def create_similarity(self, chunk_a_id, chunk_b_id, score: float) -> None:
                pass

            async def find_similar_chunks(
                self, embedding: list[float], limit: int = 20, threshold: float = 0.7
            ) -> list[tuple]:
                return []

            async def get_note_relationships(self, note_id) -> dict:
                return {}

            async def get_all_notes(self) -> list:
                return []

            async def get_all_chunks(self) -> list:
                return []

            async def derive_related_to(self, threshold: float = 0.7) -> int:
                return 0

            # get_chunks_for_note intentionally omitted

        with pytest.raises(TypeError):
            IncompleteGraphStore()

    @pytest.mark.unit
    def test_graph_store_complete_subclass(self):
        """Contract: Subclass implementing ALL abstract methods instantiates successfully."""

        class ConcreteGraphStore(GraphStore):
            async def initialize(self) -> None:
                pass

            async def close(self) -> None:
                pass

            async def upsert_note(self, note) -> None:
                pass

            async def upsert_chunk(self, chunk) -> None:
                pass

            async def create_link(self, from_note_id, to_note_id, rel_type: str) -> None:
                pass

            async def create_similarity(self, chunk_a_id, chunk_b_id, score: float) -> None:
                pass

            async def find_similar_chunks(
                self, embedding: list[float], limit: int = 20, threshold: float = 0.7
            ) -> list[tuple]:
                return []

            async def get_note_relationships(self, note_id) -> dict:
                return {}

            async def get_all_notes(self) -> list:
                return []

            async def get_chunks_for_note(self, note_id) -> list:
                return []

            async def get_all_chunks(self) -> list:
                return []

            async def derive_related_to(self, threshold: float = 0.7) -> int:
                return 0

            async def clear_semantic_edges(self) -> dict:
                return {"similarity_edges_deleted": 0, "related_to_edges_deleted": 0}

            async def get_note_relationships_with_scores(self, note_id) -> dict:
                return {}

            async def get_note_by_id(self, note_id) -> None:
                return None

            async def get_note_by_title(self, title: str) -> None:
                return None

            async def get_stats(self) -> dict:
                return {
                    "note_count": 0,
                    "chunk_count": 0,
                    "similarity_edge_count": 0,
                    "related_to_edge_count": 0,
                    "links_to_edge_count": 0,
                    "vault_names": [],
                }

            async def search_notes(self, query_embedding, limit=10, vault_filter=None) -> list:
                return []

        store = ConcreteGraphStore()
        assert store is not None
