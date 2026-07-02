from __future__ import annotations
import logging
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

_REVIEW_COLLECTION = "reviews"
_INSIGHT_COLLECTION = "insights"
_VERBATIM_COLLECTION = "verbatims"


class ChromaManager:
    """
    Manages three ChromaDB collections:
      - reviews   : clean_text embeddings for semantic review search
      - insights  : title+description embeddings for NL insight lookup
      - verbatims : direct quote embeddings for evidence retrieval
    """

    def __init__(
        self,
        persist_dir: str = "data/chroma",
        embedding_model: str = "all-MiniLM-L6-v2",
        batch_size: int = 512,
    ):
        self._persist_dir = persist_dir
        self._embedding_model = embedding_model
        self._batch_size = batch_size
        self._client: Any = None
        self._ef: Any = None
        self._collections: dict[str, Any] = {}

    def connect(self) -> None:
        import chromadb
        from chromadb.utils import embedding_functions

        Path(self._persist_dir).mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(path=self._persist_dir)
        self._ef = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name=self._embedding_model
        )
        for name in (_REVIEW_COLLECTION, _INSIGHT_COLLECTION, _VERBATIM_COLLECTION):
            self._collections[name] = self._client.get_or_create_collection(
                name=name, embedding_function=self._ef
            )
        logger.info("ChromaDB connected at %s (model=%s)", self._persist_dir, self._embedding_model)

    def _col(self, name: str) -> Any:
        if name not in self._collections:
            raise RuntimeError("Call connect() first")
        return self._collections[name]

    # ------------------------------------------------------------------
    # Reviews
    # ------------------------------------------------------------------
    def upsert_reviews(self, rows: list[dict]) -> int:
        """rows: [{id, clean_text, platform, sentiment, quality_score, ...}]"""
        return self._upsert_to(
            collection=_REVIEW_COLLECTION,
            rows=rows,
            text_field="clean_text",
            meta_fields=["platform", "sentiment", "sentiment_score",
                         "discovery_friction_detected", "user_segment_signal",
                         "quality_score", "language"],
        )

    # ------------------------------------------------------------------
    # Insights
    # ------------------------------------------------------------------
    def upsert_insights(self, rows: list[dict]) -> int:
        """rows: [{id, title, description, insight_type, opportunity_score, ...}]"""
        enriched = []
        for r in rows:
            enriched.append({
                **r,
                "_text": f"{r.get('title', '')} {r.get('description', '')}",
            })
        return self._upsert_to(
            collection=_INSIGHT_COLLECTION,
            rows=enriched,
            text_field="_text",
            meta_fields=["insight_type", "confidence_score", "opportunity_score",
                         "discovery_friction_related", "affected_segment", "review_required"],
        )

    # ------------------------------------------------------------------
    # Verbatims (evidence quotes)
    # ------------------------------------------------------------------
    def upsert_verbatims(self, insight_id: str, verbatims: list[str]) -> int:
        if not verbatims:
            return 0
        rows = [
            {"id": f"{insight_id}_{i}", "_text": v, "insight_id": insight_id}
            for i, v in enumerate(verbatims)
        ]
        return self._upsert_to(
            collection=_VERBATIM_COLLECTION,
            rows=rows,
            text_field="_text",
            meta_fields=["insight_id"],
        )

    # ------------------------------------------------------------------
    # Semantic search
    # ------------------------------------------------------------------
    def search_reviews(
        self,
        query: str,
        n_results: int = 10,
        where: Optional[dict] = None,
    ) -> list[dict]:
        col = self._col(_REVIEW_COLLECTION)
        kwargs: dict = {"query_texts": [query], "n_results": min(n_results, col.count() or 1)}
        if where:
            kwargs["where"] = where
        result = col.query(**kwargs)
        return self._flatten_result(result)

    def search_insights(self, query: str, n_results: int = 10) -> list[dict]:
        col = self._col(_INSIGHT_COLLECTION)
        result = col.query(
            query_texts=[query],
            n_results=min(n_results, col.count() or 1),
        )
        return self._flatten_result(result)

    def search_verbatims(self, query: str, n_results: int = 5) -> list[dict]:
        col = self._col(_VERBATIM_COLLECTION)
        result = col.query(
            query_texts=[query],
            n_results=min(n_results, col.count() or 1),
        )
        return self._flatten_result(result)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _upsert_to(
        self,
        collection: str,
        rows: list[dict],
        text_field: str,
        meta_fields: list[str],
    ) -> int:
        col = self._col(collection)
        total = 0
        for i in range(0, len(rows), self._batch_size):
            chunk = rows[i: i + self._batch_size]
            ids = [r["id"] for r in chunk]
            documents = [str(r.get(text_field, "")) for r in chunk]
            metadatas = [
                {k: self._safe_meta(r.get(k)) for k in meta_fields}
                for r in chunk
            ]
            col.upsert(ids=ids, documents=documents, metadatas=metadatas)
            total += len(chunk)
        logger.debug("Upserted %d to collection '%s'", total, collection)
        return total

    @staticmethod
    def _safe_meta(value: Any) -> Any:
        """ChromaDB metadata must be str/int/float/bool — no None or lists."""
        if value is None:
            return ""
        if isinstance(value, (str, int, float, bool)):
            return value
        return str(value)

    @staticmethod
    def _flatten_result(result: dict) -> list[dict]:
        out = []
        ids = result.get("ids", [[]])[0]
        docs = result.get("documents", [[]])[0]
        metas = result.get("metadatas", [[]])[0]
        distances = result.get("distances", [[]])[0]
        for i, _id in enumerate(ids):
            out.append({
                "id": _id,
                "document": docs[i] if i < len(docs) else "",
                "metadata": metas[i] if i < len(metas) else {},
                "distance": distances[i] if i < len(distances) else None,
            })
        return out

    def collection_counts(self) -> dict[str, int]:
        return {name: col.count() for name, col in self._collections.items()}
