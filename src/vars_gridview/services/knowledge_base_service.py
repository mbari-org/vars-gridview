"""Knowledge-base service with TTL caching.

This module provides :class:`KnowledgeBaseService`, which wraps the
:class:`~vars_gridview.lib.m3.clients.VARSKBServerClient` and caches
expensive KB lookups (concept list, parts list, concept names) using
:class:`~cachetools.TTLCache`.
"""

from __future__ import annotations

import logging
from typing import Optional

import requests
from cachetools import TTLCache

from vars_gridview.lib.m3.clients import VARSKBServerClient, VampireSquidClient

_log = logging.getLogger(__name__)

# Default TTL for cached KB data (15 minutes).
_DEFAULT_TTL = 900


class KnowledgeBaseService:
    """Cached wrapper around the VARS KB server and Vampire Squid.

    All network calls are cached with a configurable TTL so that frequent
    UI operations (concept autocomplete, parts list popup) do not hammer
    the back-end services.

    Args:
        kb_client: Authenticated :class:`VARSKBServerClient`.
        vampire_squid: Authenticated :class:`VampireSquidClient`.
        ttl: Cache time-to-live in seconds (default: 15 minutes).
    """

    def __init__(
        self,
        kb_client: VARSKBServerClient,
        vampire_squid: VampireSquidClient,
        ttl: int = _DEFAULT_TTL,
    ) -> None:
        self._kb = kb_client
        self._vs = vampire_squid
        self._ttl = ttl

        # Caches populated lazily.
        self._concepts: Optional[dict[str, Optional[str]]] = None
        self._parts: Optional[list[str]] = None
        self._video_sequence_names: Optional[list[str]] = None
        self._concept_name_cache: TTLCache = TTLCache(maxsize=512, ttl=ttl)

    # ── Concepts ───────────────────────────────────────────────────────────────

    def get_concepts(self) -> dict[str, Optional[str]]:
        """Return all concept names mapped to their common names (lazy).

        Common names are ``None`` until :meth:`get_concept_name` is called.

        Returns:
            Dict mapping concept name → common name (or ``None``).

        Raises:
            requests.HTTPError: On network failure.
        """
        if self._concepts is None:
            response = self._kb.get_concepts()
            response.raise_for_status()
            self._concepts = {name: None for name in response.json()}
            _log.debug(f"Loaded {len(self._concepts)} KB concepts")
        return self._concepts

    def get_concept_name(self, concept: str) -> Optional[str]:
        """Return the common name for *concept*, fetching it if not cached.

        Args:
            concept: Scientific concept name.

        Returns:
            The common name string, or ``None`` if not found.

        Raises:
            requests.HTTPError: On network failure.
        """
        if concept in self._concept_name_cache:
            return self._concept_name_cache[concept]

        concepts = self.get_concepts()
        if concepts.get(concept) is None:
            try:
                response = self._kb.get_concept(concept)
                response.raise_for_status()
                name: Optional[str] = response.json().get("name")
            except requests.HTTPError:
                name = None
            concepts[concept] = name
            self._concept_name_cache[concept] = name

        return concepts.get(concept)

    def get_descendants(self, concept: str) -> list[str]:
        """Return all taxa in the phylogenetic subtree rooted at *concept*.

        Args:
            concept: Root concept name.

        Returns:
            List of descendant concept names (including *concept* itself).
            Returns an empty list if *concept* is not found.

        Raises:
            requests.HTTPError: On network failure other than 404.
        """
        response = self._kb.get_phylogeny_taxa(concept)
        if response.status_code == 404:
            return []
        response.raise_for_status()
        names = [taxon["name"] for taxon in response.json()]
        _log.debug(f"Got {len(names)} descendants of {concept!r}")
        return names

    # ── Parts ──────────────────────────────────────────────────────────────────

    def get_parts(self) -> list[str]:
        """Return all organism-part names (cached for the process lifetime).

        Returns:
            List of part name strings.

        Raises:
            requests.HTTPError: On network failure.
        """
        if self._parts is None:
            response = self._kb.get_parts()
            response.raise_for_status()
            self._parts = [part["name"] for part in response.json()]
            _log.debug(f"Loaded {len(self._parts)} KB parts")
        return self._parts

    # ── Video sequences ────────────────────────────────────────────────────────

    def get_video_sequence_names(self) -> list[str]:
        """Return all video sequence names (cached).

        Returns:
            Sorted list of sequence name strings.

        Raises:
            requests.HTTPError: On network failure.
        """
        if self._video_sequence_names is None:
            response = self._vs.get_video_sequence_names()
            response.raise_for_status()
            self._video_sequence_names = response.json()
            _log.debug(f"Loaded {len(self._video_sequence_names)} video sequence names")
        return self._video_sequence_names

    def invalidate(self) -> None:
        """Clear all in-memory caches (e.g. on re-login)."""
        self._concepts = None
        self._parts = None
        self._video_sequence_names = None
        self._concept_name_cache.clear()


__all__ = ["KnowledgeBaseService"]
