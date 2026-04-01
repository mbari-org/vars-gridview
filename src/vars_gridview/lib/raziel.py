"""Raziel authentication and endpoint discovery.

Raziel is the MBARI service registry.  This module provides a single
function, :func:`authenticate`, that exchanges user credentials for a
JWT and then fetches the list of M3 microservice endpoint descriptors.
"""

from __future__ import annotations

from base64 import b64encode

import requests


def authenticate(url: str, username: str, password: str) -> list[dict]:
    """Authenticate with Raziel and return the endpoint list.

    Performs a two-step exchange:

    1. POST ``/auth`` with HTTP Basic credentials to obtain a JWT.
    2. GET ``/endpoints`` with the JWT to retrieve microservice URLs.

    Args:
        url: Base URL of the Raziel server (no trailing slash).
        username: VARS account username.
        password: VARS account password.

    Returns:
        List of endpoint descriptor dicts, each containing at minimum
        ``"name"``, ``"url"``, and ``"secret"`` keys.

    Raises:
        requests.HTTPError: If either HTTP request fails.
    """
    credentials = b64encode(f"{username}:{password}".encode()).decode()
    auth_header = f"Basic {credentials}"

    res = requests.post(f"{url}/auth", headers={"Authorization": auth_header})
    res.raise_for_status()

    token: str = res.json()["accessToken"]

    endpoints_res = requests.get(
        f"{url}/endpoints", headers={"Authorization": f"Bearer {token}"}
    )
    endpoints_res.raise_for_status()
    return endpoints_res.json()


__all__ = ["authenticate"]
