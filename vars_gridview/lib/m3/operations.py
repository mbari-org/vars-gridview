"""
M3 operations. Make use of the clients defined in __init__.py.
"""

import json
from datetime import datetime
from typing import List

import requests

from vars_gridview.lib import m3
from vars_gridview.lib.log import LOGGER

KB_CONCEPTS = None
KB_PARTS = None
USERS = None


def get_kb_concepts() -> List[str]:
    """
    Get a list of all concepts in the KB.
    """
    global KB_CONCEPTS
    if not KB_CONCEPTS:
        LOGGER.debug("Getting concepts from KB")
        response = m3.VARS_KB_SERVER_CLIENT.get_concepts()

        response.raise_for_status()
        KB_CONCEPTS = response.json()
        LOGGER.debug(f"Got {len(KB_CONCEPTS)} concepts from KB")

    return KB_CONCEPTS


def get_kb_parts() -> List[str]:
    """
    Get a list of all parts in the KB.
    """
    global KB_PARTS
    if not KB_PARTS:
        LOGGER.debug("Getting parts from KB")
        response = m3.VARS_KB_SERVER_CLIENT.get_parts()

        response.raise_for_status()
        KB_PARTS = [part["name"] for part in response.json()]
        LOGGER.debug(f"Got {len(KB_PARTS)} parts from KB")

    return KB_PARTS


def get_kb_descendants(concept: str) -> List[str]:
    """
    Get a list of all descendants of a concept in the KB, including the concept.
    """
    LOGGER.debug(f"Getting descendants of {concept} from KB")
    response = m3.VARS_KB_SERVER_CLIENT.get_phylogeny_taxa(concept)

    if response.status_code == 404:
        return []  # concept not found, so no descendants
    else:
        response.raise_for_status()

    parsed_response = response.json()
    taxa_names = [taxa["name"] for taxa in parsed_response]
    LOGGER.debug(f"Got {len(taxa_names)} descendants of {concept} from KB")
    return taxa_names


def get_users() -> List[dict]:
    """
    Get a list of all users as dicts.
    """
    global USERS
    if not USERS:
        LOGGER.debug("Getting users from VARS user server")
        response = m3.VARS_USER_SERVER_CLIENT.get_all_users()

        response.raise_for_status()
        USERS = response.json()
        LOGGER.debug(f"Got {len(USERS)} users from VARS user server")

    return USERS


def update_bounding_box_data(association_uuid: str, box_dict: dict) -> dict:
    """
    Update a bounding box's JSON data (link_value field of association).
    """
    request_data = {
        "link_value": json.dumps(box_dict),
    }

    LOGGER.debug(f"Updating bounding box data for {association_uuid}:\n{request_data}")
    response = m3.ANNOSAURUS_CLIENT.update_association(association_uuid, request_data)
    response.raise_for_status()
    return response.json()


def update_bounding_box_part(association_uuid: str, part: str) -> dict:
    """
    Update a bounding box's part (to_concept field of association).
    """
    request_data = {
        "to_concept": part,
    }

    LOGGER.debug(f"Updating bounding box part for {association_uuid}:\n{request_data}")
    response = m3.ANNOSAURUS_CLIENT.update_association(association_uuid, request_data)
    response.raise_for_status()
    return response.json()


def update_observation_concept(
    observation_uuid: str, concept: str, observer: str
) -> dict:
    """
    Update an observation's concept and observer.
    """
    request_data = {
        "concept": concept,
        "observer": observer,  # when we update the concept, we also update the observer
    }

    LOGGER.debug(f"Updating observation concept for {observation_uuid}:\n{request_data}")
    response = m3.ANNOSAURUS_CLIENT.update_observation(observation_uuid, request_data)

    response.raise_for_status()
    return response.json()


def create_association(association: dict) -> requests.Response:
    """
    Create an association.
    """
    LOGGER.debug(f"Creating association:\n{association}")
    response = m3.ANNOSAURUS_CLIENT.create_association(association)

    response.raise_for_status()
    return response


def delete_association(association_uuid: str):
    """
    Delete an association.
    
    Args:
        association_uuid: UUID of the association to delete.
    """
    LOGGER.debug(f"Deleting association {association_uuid}")
    response = m3.ANNOSAURUS_CLIENT.delete_association(association_uuid)

    response.raise_for_status()


def get_observation(observation_uuid: str) -> requests.Response:
    """
    Get an observation by UUID.
    """
    LOGGER.debug(f"Getting observation {observation_uuid}")
    response = m3.ANNOSAURUS_CLIENT.get_observation(observation_uuid)
    
    response.raise_for_status()
    return response.json()


def create_observation(observation: dict) -> requests.Response:
    """
    Create an observation.
    """
    LOGGER.debug(f"Creating observation:\n{observation}")
    response = m3.ANNOSAURUS_CLIENT.create_observation(observation)

    response.raise_for_status()
    return response


def delete_observation(observation_uuid: str):
    """
    Delete an observation.
    
    Args:
        observation_uuid: UUID of the observation to delete.
    """
    LOGGER.debug(f"Deleting observation {observation_uuid}")
    response = m3.ANNOSAURUS_CLIENT.delete_observation(observation_uuid)
    
    response.raise_for_status()


def get_videos_at_datetime(dt: datetime) -> List[dict]:
    """
    Get a list of videos occurring at a given instant.
    """
    timestamp = dt.strftime("%Y-%m-%dT%H:%M:%S.%fZ")

    LOGGER.debug(f"Getting videos at {timestamp}")
    response = m3.VAMPIRE_SQUID_CLIENT.get_videos_at_timestamp(timestamp)

    response.raise_for_status()
    return response.json()


def get_vars_imaged_moment(image_reference_uuid: str) -> dict:
    """
    Get MBARI VARS imaged moment by UUID.
    This will not work unless you are connected to the MBARI network!
    """
    LOGGER.debug(f"Getting VARS imaged moment {image_reference_uuid}")
    response = requests.get(
        "http://m3.shore.mbari.org/anno/v1/imagedmoments/" + image_reference_uuid
    )

    return response.json()
