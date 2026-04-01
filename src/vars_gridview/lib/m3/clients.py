"""M3 REST API clients.

This module provides a base :class:`M3Client` built on :mod:`requests`, plus
one concrete subclass per M3 microservice.  Two decorators — :func:`needs_auth`
and :func:`reauth` — handle API-key JWT authentication and transparent
re-authentication on 401/403 responses.
"""

from __future__ import annotations

from collections.abc import Callable
from functools import wraps
from typing import Any, Optional, TypeVar

import requests
import requests.auth

from vars_gridview.lib.m3.query import QueryRequest

R = TypeVar("R")


class JWTAuth(requests.auth.AuthBase):
    """Attaches a Bearer JWT to every outgoing request.

    Args:
        token: The raw JWT string obtained from an ``/auth`` endpoint.
    """

    def __init__(self, token: str) -> None:
        self._token = token

    def __call__(self, r: requests.PreparedRequest) -> requests.PreparedRequest:
        if r.headers is None:
            r.headers = {}
        r.headers["Authorization"] = f"BEARER {self._token}"
        return r


class NotAuthenticated(Exception):
    """Raised when a protected method is called on an unauthenticated client."""


def needs_auth(
    f: Callable[..., R],
) -> Callable[..., R]:
    """Decorator — raise :exc:`NotAuthenticated` if the client has no session auth.

    Args:
        f: The bound method to guard.

    Returns:
        The wrapped method.
    """

    @wraps(f)
    def wrapper(self: M3Client, *args: Any, **kwargs: Any) -> R:
        if not self.authenticated:
            raise NotAuthenticated
        return f(self, *args, **kwargs)

    return wrapper


def reauth(
    f: Callable[..., R],
) -> Callable[..., R]:
    """Decorator — re-authenticate and retry once on auth failures.

    Handles :exc:`NotAuthenticated` and HTTP 401/403 responses by calling
    :meth:`M3Client.authenticate` then retrying *f* exactly once.

    Args:
        f: The bound method to wrap.

    Returns:
        The wrapped method.
    """

    @wraps(f)
    def wrapper(self: M3Client, *args: Any, **kwargs: Any) -> R:
        try:
            return f(self, *args, **kwargs)
        except NotAuthenticated:
            self.authenticate()
            return f(self, *args, **kwargs)
        except requests.HTTPError as exc:
            if exc.response is not None and exc.response.status_code in (401, 403):
                self.authenticate()
                return f(self, *args, **kwargs)
            raise

    return wrapper


class M3Client:
    """Base HTTP client for an M3 microservice.

    Maintains a :class:`~requests.Session` and provides convenience wrappers
    for the four HTTP methods used by M3 (GET, PUT, POST, DELETE).

    Args:
        base_url: Root URL of the service (trailing slashes are stripped).
        api_key: If provided, :meth:`authenticate` is called immediately.
    """

    def __init__(self, base_url: str, api_key: Optional[str] = None) -> None:
        self._session = requests.Session()
        self._api_key: Optional[str] = api_key
        self.base_url = base_url  # uses the setter to strip trailing slash
        if api_key is not None:
            self.authenticate(api_key)

    # ── Properties ─────────────────────────────────────────────────────────────

    @property
    def base_url(self) -> str:
        """Root URL of the service."""
        return self._base_url

    @base_url.setter
    def base_url(self, value: str) -> None:
        self._base_url = value.rstrip("/")

    @property
    def api_key(self) -> Optional[str]:
        """API key supplied at construction (may be ``None``)."""
        return self._api_key

    @property
    def authenticated(self) -> bool:
        """``True`` if the session has a :class:`JWTAuth` attached."""
        return self._session.auth is not None

    # ── HTTP helpers ────────────────────────────────────────────────────────────

    def url_to(self, path: str) -> str:
        """Prepend the base URL to *path*.

        Args:
            path: Relative path (should start with ``/``).

        Returns:
            Absolute URL string.
        """
        return self._base_url + path

    def get(self, path: str, **kwargs) -> requests.Response:
        """Send a GET request to *path*."""
        return self._session.get(self.url_to(path), **kwargs)

    def put(self, path: str, **kwargs) -> requests.Response:
        """Send a PUT request to *path*."""
        return self._session.put(self.url_to(path), **kwargs)

    def post(self, path: str, **kwargs) -> requests.Response:
        """Send a POST request to *path*."""
        return self._session.post(self.url_to(path), **kwargs)

    def delete(self, path: str, **kwargs) -> requests.Response:
        """Send a DELETE request to *path*."""
        return self._session.delete(self.url_to(path), **kwargs)

    # ── Authentication ──────────────────────────────────────────────────────────

    def authenticate(
        self, api_key: Optional[str] = None, auth_path: str = "/auth"
    ) -> None:
        """Exchange an API key for a JWT and attach it to the session.

        Args:
            api_key: API key to use.  Falls back to the key supplied at
                construction.  Raises :exc:`ValueError` if neither is set.
            auth_path: Path of the authentication endpoint.

        Raises:
            ValueError: If no API key is available.
            requests.HTTPError: If the auth request fails.
        """
        self._session.auth = None
        api_key = api_key or self._api_key
        if api_key is None:
            raise ValueError("An API key is required for authentication")

        response = self.post(auth_path, headers={"Authorization": f"APIKEY {api_key}"})
        response.raise_for_status()

        token: str = response.json()["access_token"]
        self._session.auth = JWTAuth(token)


class AnnosaurusClient(M3Client):
    """Client for the Annosaurus annotation-database REST API (v1)."""

    @reauth
    @needs_auth
    def create_association(self, data: dict) -> requests.Response:
        """Create a new association."""
        return self.post("/associations", data=data)

    @reauth
    @needs_auth
    def update_association(
        self, association_uuid: str, data: dict
    ) -> requests.Response:
        """Update an existing association by UUID."""
        return self.put(f"/associations/{association_uuid}", data=data)

    @reauth
    @needs_auth
    def delete_association(self, association_uuid: str) -> requests.Response:
        """Delete an association by UUID."""
        return self.delete(f"/associations/{association_uuid}")

    def get_observation(self, observation_uuid: str) -> requests.Response:
        """Fetch an observation by UUID."""
        return self.get(f"/observations/{observation_uuid}")

    @reauth
    @needs_auth
    def create_observation(self, data: dict) -> requests.Response:
        """Create a new annotation (imaged-moment + observation + associations)."""
        return self.post("/annotations", data=data)

    @reauth
    @needs_auth
    def update_observation(
        self, observation_uuid: str, data: dict
    ) -> requests.Response:
        """Update an existing observation by UUID."""
        return self.put(f"/observations/{observation_uuid}", data=data)

    @reauth
    @needs_auth
    def delete_observation(self, observation_uuid: str) -> requests.Response:
        """Delete an observation by UUID."""
        return self.delete(f"/observations/{observation_uuid}")

    def get_imaged_moment(self, imaged_moment_uuid: str) -> requests.Response:
        """Fetch an imaged moment by UUID."""
        return self.get(f"/imagedmoments/{imaged_moment_uuid}")

    def get_image_reference(self, image_reference_uuid: str) -> requests.Response:
        """Fetch an image reference by UUID."""
        return self.get(f"/imagereferences/{image_reference_uuid}")

    def query(self, query_request: QueryRequest) -> requests.Response:
        """Run a TSV query against ``/query/run``."""
        return self.post("/query/run", json=query_request.to_dict())

    def count(self, query_request: QueryRequest) -> requests.Response:
        """Return the row count for a query via ``/query/count``."""
        return self.post("/query/count", json=query_request.to_dict())

    def query_download(self, query_request: QueryRequest) -> requests.Response:
        """Run a full-download query against ``/query/download``."""
        return self.post("/query/download", json=query_request.to_dict())

    # Alias kept for callers that use query_count spelling.
    query_count = count


class VampireSquidClient(M3Client):
    """Client for the Vampire Squid video-index REST API (v1)."""

    def get_videos_at_timestamp(self, timestamp: str) -> requests.Response:
        """Fetch videos covering the given ISO-8601 timestamp."""
        return self.get(f"/videos/timestamp/{timestamp}")

    def get_video_by_video_reference_uuid(
        self, video_reference_uuid: str
    ) -> requests.Response:
        """Fetch metadata for a single video reference."""
        return self.get(f"/videos/videoreference/{video_reference_uuid}")

    def get_video_sequence_names(self) -> requests.Response:
        """Return all video sequence names."""
        return self.get("/videosequences/names")

    def get_video_sequence_by_name(self, name: str) -> requests.Response:
        """Fetch a video sequence by its name."""
        return self.get(f"/videosequences/name/{name}")


class VARSUserServerClient(M3Client):
    """Client for the VARS user-server REST API (v1)."""

    def get_all_users(self) -> requests.Response:
        """Return all VARS user accounts."""
        return self.get("/users")


class VARSKBServerClient(M3Client):
    """Client for the VARS knowledge-base server REST API (v1)."""

    def get_concepts(self) -> requests.Response:
        """Return all concept names in the KB."""
        return self.get("/concept")

    def get_concept(self, concept: str) -> requests.Response:
        """Fetch metadata for a single concept."""
        return self.get(f"/concept/{concept}")

    def get_parts(self) -> requests.Response:
        """Return all organism-part names (``/phylogeny/taxa/organism part``)."""
        return self.get("/phylogeny/taxa/organism part")

    def get_phylogeny_taxa(self, concept: str) -> requests.Response:
        """Return all taxa in the phylogenetic subtree rooted at *concept*."""
        return self.get(f"/phylogeny/taxa/{concept}")


class SkimmerClient(M3Client):
    """Client for the Skimmer image-crop service."""

    def crop(
        self,
        url: str,
        left: int,
        top: int,
        right: int,
        bottom: int,
        ms: Optional[int] = None,
    ) -> requests.Response:
        """Request a cropped sub-image from a frame URL.

        Args:
            url: Source frame image URL.
            left: Left pixel of the crop region.
            top: Top pixel of the crop region.
            right: Right pixel of the crop region.
            bottom: Bottom pixel of the crop region.
            ms: Optional elapsed-time offset in milliseconds for video frames.

        Returns:
            HTTP response whose body is the cropped JPEG/PNG image.
        """
        params: dict = {
            "url": url,
            "left": left,
            "top": top,
            "right": right,
            "bottom": bottom,
        }
        if ms is not None:
            params["ms"] = ms
        return self.get("/crop", params=params)


__all__ = [
    "JWTAuth",
    "NotAuthenticated",
    "needs_auth",
    "reauth",
    "M3Client",
    "AnnosaurusClient",
    "VampireSquidClient",
    "VARSUserServerClient",
    "VARSKBServerClient",
    "SkimmerClient",
]
