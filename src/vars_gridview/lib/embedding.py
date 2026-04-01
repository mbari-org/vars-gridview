"""Image embedding utilities.

This module provides an abstract :class:`Embedding` base class and a concrete
HTTP-backed implementation that talks to the MBARI multi-model embedding
service.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Callable, Iterable
from urllib.parse import quote

import cv2
import numpy as np
import requests


class Embedding(ABC):
    """Abstract base class for image embedding models.

    Subclasses must implement :meth:`embed` to convert an RGB NumPy array into
    a flat feature vector.
    """

    @abstractmethod
    def embed(self, image: np.ndarray) -> np.ndarray:
        """Embed an image into a feature vector.

        Args:
            image: RGB image as an ``(H, W, 3)`` uint8 NumPy array.

        Returns:
            1-D float32 embedding vector of shape ``(n,)``.
        """

    def embed_many(
        self,
        images: Iterable[np.ndarray],
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> list[np.ndarray]:
        """Embed multiple images; default implementation calls :meth:`embed` per image."""
        image_list = list(images)
        total = len(image_list)
        if progress_callback is not None:
            progress_callback(0, total)
        vectors = []
        for index, image in enumerate(image_list, start=1):
            vectors.append(self.embed(image))
            if progress_callback is not None:
                progress_callback(index, total)
        return vectors


class HttpEmbedding(Embedding):
    """Image embedding client backed by the MBARI embedding API service."""

    _MAX_IMAGE_BATCH_SIZE = 64

    def __init__(
        self,
        *,
        base_url: str,
        model_name: str,
        timeout_seconds: float = 30.0,
    ) -> None:
        self._base_url = base_url.strip().rstrip("/")
        self._model_name = model_name.strip()
        self._timeout_seconds = timeout_seconds

    @property
    def model_name(self) -> str:
        return self._model_name

    def health_check(self) -> None:
        """Raise if the embedding service is unreachable or unhealthy."""
        response = requests.get(
            f"{self._base_url}/health",
            timeout=self._timeout_seconds,
        )
        response.raise_for_status()

    @staticmethod
    def list_image_models(
        base_url: str,
        timeout_seconds: float = 15.0,
    ) -> list[str]:
        """Return available image-capable model names from the embedding service."""
        response = requests.get(
            f"{base_url.strip().rstrip('/')}/models",
            timeout=timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
        models = payload.get("models", {})
        if not isinstance(models, dict):
            return []

        image_models: list[str] = []
        for model_name, metadata in models.items():
            if not isinstance(model_name, str):
                continue
            if HttpEmbedding._is_image_model(model_name, metadata):
                image_models.append(model_name)

        return sorted(set(image_models))

    def embed(self, image: np.ndarray) -> np.ndarray:
        embeddings = self.embed_many([image])
        if not embeddings:
            raise RuntimeError("Embedding service returned no embedding")
        return embeddings[0]

    def embed_many(
        self,
        images: Iterable[np.ndarray],
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> list[np.ndarray]:
        image_list = list(images)
        if not image_list:
            return []

        total = len(image_list)
        processed = 0
        if progress_callback is not None:
            progress_callback(0, total)

        all_vectors: list[np.ndarray] = []
        for start in range(0, len(image_list), self._MAX_IMAGE_BATCH_SIZE):
            batch = image_list[start : start + self._MAX_IMAGE_BATCH_SIZE]
            all_vectors.extend(self._embed_many_batch(batch))
            processed += len(batch)
            if progress_callback is not None:
                progress_callback(processed, total)

        return all_vectors

    def _embed_many_batch(self, image_list: list[np.ndarray]) -> list[np.ndarray]:
        """Embed one bounded-size batch and return vectors in input order."""
        if not image_list:
            return []

        files: list[tuple[str, tuple[str, bytes, str]]] = []
        for index, image in enumerate(image_list):
            png_bytes = self._encode_png_bytes(image)
            files.append(
                (
                    "files",
                    (f"image_{index}.png", png_bytes, "image/png"),
                )
            )

        model_segment = quote(self._model_name, safe="")
        response = requests.post(
            f"{self._base_url}/embed/image/{model_segment}",
            files=files,
            timeout=self._timeout_seconds,
        )
        if response.status_code == 400:
            detail = HttpEmbedding._response_detail(response)
            available = []
            try:
                available = HttpEmbedding.list_image_models(
                    self._base_url,
                    timeout_seconds=self._timeout_seconds,
                )
            except Exception:
                pass
            if available and self._model_name not in available:
                raise RuntimeError(
                    f"Embedding model '{self._model_name}' is not available. "
                    f"Available image models: {', '.join(available)}"
                )
            raise RuntimeError(f"Embedding request rejected (400): {detail}")

        response.raise_for_status()

        payload = response.json()
        vectors = payload.get("embeddings", [])
        if len(vectors) != len(image_list):
            raise RuntimeError(
                "Embedding service returned mismatched embedding count "
                f"({len(vectors)} for {len(image_list)} images)"
            )

        return [np.asarray(vector, dtype=np.float32).flatten() for vector in vectors]

    @staticmethod
    def _encode_png_bytes(image: np.ndarray) -> bytes:
        """Return PNG-encoded bytes for an image array."""
        array = np.asarray(image)
        if array.ndim != 3 or array.shape[2] != 3:
            raise RuntimeError(
                f"Expected HxWx3 image for embedding, got shape {array.shape}"
            )
        if array.dtype != np.uint8:
            array = np.clip(array, 0, 255).astype(np.uint8)
        array = np.ascontiguousarray(array)
        ok, encoded = cv2.imencode(".png", array)
        if not ok:
            raise RuntimeError("Failed to PNG-encode image for embedding request")
        return encoded.tobytes()

    @staticmethod
    def _response_detail(response: requests.Response) -> str:
        try:
            payload = response.json()
            detail = payload.get("detail")
            if detail is not None:
                return str(detail)
            return str(payload)
        except Exception:
            return response.text or "Unknown error"

    @staticmethod
    def _is_image_model(model_name: str, metadata: object) -> bool:
        lower_name = model_name.lower()
        if "image" in lower_name:
            return True
        if not isinstance(metadata, dict):
            return False
        for value in metadata.values():
            if isinstance(value, str) and "image" in value.lower():
                return True
            if isinstance(value, list):
                for item in value:
                    if isinstance(item, str) and "image" in item.lower():
                        return True
        return False


__all__ = ["Embedding", "HttpEmbedding"]
