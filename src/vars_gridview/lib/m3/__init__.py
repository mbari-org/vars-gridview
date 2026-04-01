"""M3 microservice context.

This module provides :class:`M3Context`, an immutable container that holds
one authenticated client for every M3 microservice used by the application.
Use :meth:`M3Context.from_endpoint_data` to construct an instance from the
list of endpoint dicts returned by Raziel.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from beholder_client import BeholderClient

from vars_gridview.lib.runtime.log import LOGGER
from vars_gridview.lib.m3.clients import (
    AnnosaurusClient,
    SkimmerClient,
    VampireSquidClient,
    VARSKBServerClient,
    VARSUserServerClient,
)


@dataclass(frozen=True)
class M3Context:
    """Immutable bundle of authenticated M3 microservice clients.

    Attributes:
        annosaurus: Annosaurus annotation-database client.
        vampire_squid: Vampire Squid video-index client.
        vars_user_server: VARS user-server client.
        vars_kb_server: VARS knowledge-base server client.
        beholder: Beholder frame-grab client.
        skimmer: Skimmer crop/thumbnail client.
    """

    annosaurus: AnnosaurusClient
    vampire_squid: VampireSquidClient
    vars_user_server: VARSUserServerClient
    vars_kb_server: VARSKBServerClient
    beholder: BeholderClient
    skimmer: SkimmerClient

    @classmethod
    def from_endpoint_data(cls, endpoints: list[dict]) -> "M3Context":
        """Construct an :class:`M3Context` from Raziel endpoint data.

        Args:
            endpoints: List of endpoint dicts, each containing at least
                ``"name"``, ``"url"``, and ``"secret"`` keys, as returned
                by :func:`~vars_gridview.lib.auth.raziel.authenticate`.

        Returns:
            A fully-initialised :class:`M3Context`.

        Raises:
            ValueError: If a required endpoint entry is missing.
        """

        def _get(name: str) -> tuple[str, Optional[str]]:
            entry = next((e for e in endpoints if e["name"] == name), None)
            if entry is None:
                raise ValueError(f'Endpoint "{name}" not found in endpoint data')
            return entry["url"], entry.get("secret")

        anno_url, anno_key = _get("annosaurus")
        annosaurus = AnnosaurusClient(anno_url)
        annosaurus.authenticate(anno_key)
        LOGGER.debug(f"Configured and authenticated Annosaurus client at {anno_url}")

        vam_url, _ = _get("vampire-squid")
        vampire_squid = VampireSquidClient(vam_url)
        LOGGER.debug(f"Configured Vampire Squid client at {vam_url}")

        users_url, _ = _get("vars-user-server")
        vars_user_server = VARSUserServerClient(users_url)
        LOGGER.debug(f"Configured VARS User Server client at {users_url}")

        kb_url, _ = _get("vars-kb-server")
        vars_kb_server = VARSKBServerClient(kb_url)
        LOGGER.debug(f"Configured VARS KB Server client at {kb_url}")

        beholder_url, beholder_key = _get("beholder")
        if beholder_key is None:
            raise ValueError('Endpoint "beholder" is missing required "secret"')
        beholder = BeholderClient(beholder_url, beholder_key)
        LOGGER.debug(f"Configured and authenticated Beholder client at {beholder_url}")

        skimmer_url, _ = _get("skimmer")
        skimmer = SkimmerClient(skimmer_url)
        LOGGER.debug(f"Configured Skimmer client at {skimmer_url}")

        return cls(
            annosaurus=annosaurus,
            vampire_squid=vampire_squid,
            vars_user_server=vars_user_server,
            vars_kb_server=vars_kb_server,
            beholder=beholder,
            skimmer=skimmer,
        )


__all__ = [
    "M3Context",
]
