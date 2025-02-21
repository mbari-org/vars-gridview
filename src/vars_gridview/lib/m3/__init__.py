from beholder_client import BeholderClient

from vars_gridview.lib.log import LOGGER
from vars_gridview.lib.m3.clients import (
    AnnosaurusClient,
    SkimmerClient,
    VampireSquidClient,
    VARSKBServerClient,
    VARSUserServerClient,
)

ANNOSAURUS_CLIENT: AnnosaurusClient = None
VAMPIRE_SQUID_CLIENT: VampireSquidClient = None
VARS_USER_SERVER_CLIENT: VARSUserServerClient = None
VARS_KB_SERVER_CLIENT: VARSKBServerClient = None
BEHOLDER_CLIENT: BeholderClient = None
SKIMMER_CLIENT: SkimmerClient = None


def setup_from_endpoint_data(endpoints: list):
    """
    Set up the clients from a list of Raziel endpoint dicts.
    Raise a ValueError if the list does not contain the required information.
    """

    def get_client_url_secret(name: str):
        data = next((e for e in endpoints if e["name"] == name), None)
        if data is None:
            raise ValueError(f'Endpoint "{name}" not found')
        return data["url"], data["secret"]

    anno_url, anno_api_key = get_client_url_secret("annosaurus")
    global ANNOSAURUS_CLIENT
    ANNOSAURUS_CLIENT = AnnosaurusClient(anno_url)
    ANNOSAURUS_CLIENT.authenticate(anno_api_key)
    LOGGER.debug(f"Configured and authenticated Annosaurus client at {anno_url}")

    vam_url, _ = get_client_url_secret("vampire-squid")
    global VAMPIRE_SQUID_CLIENT
    VAMPIRE_SQUID_CLIENT = VampireSquidClient(vam_url)
    LOGGER.debug(f"Configured Vampire Squid client at {vam_url}")

    users_url, _ = get_client_url_secret("vars-user-server")
    global VARS_USER_SERVER_CLIENT
    VARS_USER_SERVER_CLIENT = VARSUserServerClient(users_url)
    LOGGER.debug(f"Configured VARS User Server client at {users_url}")

    kb_url, _ = get_client_url_secret("vars-kb-server")
    global VARS_KB_SERVER_CLIENT
    VARS_KB_SERVER_CLIENT = VARSKBServerClient(kb_url)
    LOGGER.debug(f"Configured VARS KB Server client at {kb_url}")

    beholder_url, beholder_api_key = get_client_url_secret("beholder")
    global BEHOLDER_CLIENT
    BEHOLDER_CLIENT = BeholderClient(beholder_url, beholder_api_key)
    LOGGER.debug(f"Configured and authenticated Beholder client at {beholder_url}")

    skimmer_url, _ = get_client_url_secret("skimmer")
    global SKIMMER_CLIENT
    SKIMMER_CLIENT = SkimmerClient(skimmer_url)
    LOGGER.debug(f"Configured Skimmer client at {skimmer_url}")
