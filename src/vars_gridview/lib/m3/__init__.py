"""M3 microservice context.

This module provides :class:`M3Context`, an immutable container that holds
one authenticated client for every M3 microservice used by the application.
Use :meth:`M3Context.from_endpoint_data` to construct an instance from the
list of endpoint dicts returned by Raziel.

Backward-compatibility shim
---------------------------
Module-level globals (``ANNOSAURUS_CLIENT``, etc.) and the old
``setup_from_endpoint_data()`` function are retained so that existing callers
continue to work.  New code should obtain clients via an :class:`M3Context`
instance instead.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from beholder_client import BeholderClient

from vars_gridview.lib.log import LOGGER
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
                by :func:`~vars_gridview.lib.raziel.authenticate`.

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


# ── Backward-compatibility module-level singletons ────────────────────────────
# These are populated by setup_from_endpoint_data() below and used by the
# legacy operations.py module. New code should use M3Context directly.

ANNOSAURUS_CLIENT: Optional[AnnosaurusClient] = None
VAMPIRE_SQUID_CLIENT: Optional[VampireSquidClient] = None
VARS_USER_SERVER_CLIENT: Optional[VARSUserServerClient] = None
VARS_KB_SERVER_CLIENT: Optional[VARSKBServerClient] = None
BEHOLDER_CLIENT: Optional[BeholderClient] = None
SKIMMER_CLIENT: Optional[SkimmerClient] = None


def setup_from_endpoint_data(endpoints: list[dict]) -> M3Context:
    """Create an :class:`M3Context` and also populate the module-level globals.

    This function exists for backward compatibility.  New code should call
    :meth:`M3Context.from_endpoint_data` directly and pass the resulting
    context via dependency injection.

    Args:
        endpoints: List of endpoint dicts from Raziel.

    Returns:
        The constructed :class:`M3Context`.
    """
    global ANNOSAURUS_CLIENT, VAMPIRE_SQUID_CLIENT, VARS_USER_SERVER_CLIENT
    global VARS_KB_SERVER_CLIENT, BEHOLDER_CLIENT, SKIMMER_CLIENT

    ctx = M3Context.from_endpoint_data(endpoints)
    ANNOSAURUS_CLIENT = ctx.annosaurus
    VAMPIRE_SQUID_CLIENT = ctx.vampire_squid
    VARS_USER_SERVER_CLIENT = ctx.vars_user_server
    VARS_KB_SERVER_CLIENT = ctx.vars_kb_server
    BEHOLDER_CLIENT = ctx.beholder
    SKIMMER_CLIENT = ctx.skimmer
    return ctx


__all__ = [
    "M3Context",
    "setup_from_endpoint_data",
    "ANNOSAURUS_CLIENT",
    "VAMPIRE_SQUID_CLIENT",
    "VARS_USER_SERVER_CLIENT",
    "VARS_KB_SERVER_CLIENT",
    "BEHOLDER_CLIENT",
    "SKIMMER_CLIENT",
]
