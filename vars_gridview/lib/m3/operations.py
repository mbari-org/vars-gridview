"""
M3 operations. Make use of the clients defined in __init__.py.
"""

import json
from datetime import datetime
from typing import Dict, List, Optional

import requests

from vars_gridview.lib import m3
from vars_gridview.lib.log import LOGGER

KB_CONCEPTS: Dict[str, Optional[str]] = None
KB_PARTS: List[str] = None
USERS = None
VIDEO_SEQUENCE_NAMES = None


def get_kb_concepts() -> Dict[str, Optional[str]]:
    """
    Get a list of all concepts in the KB.
    """
    global KB_CONCEPTS
    if not KB_CONCEPTS:
        LOGGER.debug("Getting concepts from KB")
        response = m3.VARS_KB_SERVER_CLIENT.get_concepts()

        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            LOGGER.debug(f"Error getting concepts from KB: {e}")
            raise e

        concept_names = response.json()
        KB_CONCEPTS = {concept: None for concept in concept_names}
        LOGGER.debug(f"Got {len(KB_CONCEPTS)} concepts from KB")

    return KB_CONCEPTS


def get_kb_name(concept: str) -> Optional[str]:
    """
    Get the name of a concept in the KB.
    """
    kb_concepts = get_kb_concepts()
    if kb_concepts.get(concept, None) is None:
        response = m3.VARS_KB_SERVER_CLIENT.get_concept(concept)

        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            LOGGER.debug(f"Error getting concept name for {concept} from KB: {e}")
            raise e

        name = response.json()["name"]
        LOGGER.debug(f"Got name {name} for concept {concept} from KB")

        kb_concepts[concept] = name

    return kb_concepts[concept]


def get_kb_parts() -> List[str]:
    """
    Get a list of all parts in the KB.
    """
    global KB_PARTS
    if not KB_PARTS:
        LOGGER.debug("Getting parts from KB")
        response = m3.VARS_KB_SERVER_CLIENT.get_parts()

        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            LOGGER.debug(f"Error getting parts from KB: {e}")
            raise e

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
        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            LOGGER.debug(f"Error getting descendants of {concept} from KB: {e}")
            raise e

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

        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            LOGGER.debug(f"Error getting users from VARS user server: {e}")
            raise e

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
    try:
        response.raise_for_status()
    except requests.exceptions.HTTPError as e:
        LOGGER.debug(f"Error updating bounding box data for {association_uuid}: {e}")
        raise e

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
    try:
        response.raise_for_status()
    except requests.exceptions.HTTPError as e:
        LOGGER.debug(f"Error updating bounding box part for {association_uuid}: {e}")
        raise e

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

    LOGGER.debug(
        f"Updating observation concept for {observation_uuid}:\n{request_data}"
    )
    response = m3.ANNOSAURUS_CLIENT.update_observation(observation_uuid, request_data)

    try:
        response.raise_for_status()
    except requests.exceptions.HTTPError as e:
        LOGGER.debug(f"Error updating observation concept for {observation_uuid}: {e}")
        raise e

    return response.json()


def create_association(association: dict) -> requests.Response:
    """
    Create an association.
    """
    LOGGER.debug(f"Creating association:\n{association}")
    response = m3.ANNOSAURUS_CLIENT.create_association(association)

    try:
        response.raise_for_status()
    except requests.exceptions.HTTPError as e:
        LOGGER.debug(f"Error creating association: {e}")
        raise e

    return response


def delete_association(association_uuid: str):
    """
    Delete an association.

    Args:
        association_uuid: UUID of the association to delete.
    """
    LOGGER.debug(f"Deleting association {association_uuid}")
    response = m3.ANNOSAURUS_CLIENT.delete_association(association_uuid)

    try:
        response.raise_for_status()
    except requests.exceptions.HTTPError as e:
        LOGGER.debug(f"Error deleting association {association_uuid}: {e}")
        raise e


def get_observation(observation_uuid: str) -> requests.Response:
    """
    Get an observation by UUID.
    """
    LOGGER.debug(f"Getting observation {observation_uuid}")
    response = m3.ANNOSAURUS_CLIENT.get_observation(observation_uuid)

    try:
        response.raise_for_status()
    except requests.exceptions.HTTPError as e:
        LOGGER.debug(f"Error getting observation {observation_uuid}: {e}")
        raise e

    return response.json()


def create_observation(observation: dict) -> requests.Response:
    """
    Create an observation.
    """
    LOGGER.debug(f"Creating observation:\n{observation}")
    response = m3.ANNOSAURUS_CLIENT.create_observation(observation)

    try:
        response.raise_for_status()
    except requests.exceptions.HTTPError as e:
        LOGGER.debug(f"Error creating observation: {e}")
        raise e

    return response


def delete_observation(observation_uuid: str):
    """
    Delete an observation.

    Args:
        observation_uuid: UUID of the observation to delete.
    """
    LOGGER.debug(f"Deleting observation {observation_uuid}")
    response = m3.ANNOSAURUS_CLIENT.delete_observation(observation_uuid)

    try:
        response.raise_for_status()
    except requests.exceptions.HTTPError as e:
        LOGGER.debug(f"Error deleting observation {observation_uuid}: {e}")
        raise e


def get_videos_at_datetime(dt: datetime) -> List[dict]:
    """
    Get a list of videos occurring at a given instant.
    """
    timestamp = dt.strftime("%Y-%m-%dT%H:%M:%S.%fZ")

    LOGGER.debug(f"Getting videos at {timestamp}")
    response = m3.VAMPIRE_SQUID_CLIENT.get_videos_at_timestamp(timestamp)

    try:
        response.raise_for_status()
    except requests.exceptions.HTTPError as e:
        LOGGER.debug(f"Error getting videos at {timestamp}: {e}")
        raise e

    return response.json()


def get_video_by_video_reference_uuid(video_reference_uuid: str) -> dict:
    """
    Get a video information by a contained video reference UUID.
    """
    LOGGER.debug(f"Getting video by video reference UUID {video_reference_uuid}")
    response = m3.VAMPIRE_SQUID_CLIENT.get_video_by_video_reference_uuid(
        video_reference_uuid
    )

    try:
        response.raise_for_status()
    except requests.exceptions.HTTPError as e:
        LOGGER.debug(
            f"Error getting video by video reference UUID {video_reference_uuid}: {e}"
        )
        raise e

    return response.json()


def get_video_sequence_by_name(name: str) -> dict:
    """
    Get a video sequence by name.
    """
    LOGGER.debug(f"Getting video sequence by name {name}")
    response = m3.VAMPIRE_SQUID_CLIENT.get_video_sequence_by_name(name)

    try:
        response.raise_for_status()
    except requests.exceptions.HTTPError as e:
        LOGGER.debug(f"Error getting video sequence by name {name}: {e}")
        raise e

    return response.json()


def get_imaged_moment(imaged_moment_uuid: str) -> dict:
    """
    Get an imaged moment by UUID.
    """
    LOGGER.debug(f"Getting imaged moment {imaged_moment_uuid}")
    response = m3.ANNOSAURUS_CLIENT.get_imaged_moment(imaged_moment_uuid)

    try:
        response.raise_for_status()
    except requests.exceptions.HTTPError as e:
        LOGGER.debug(f"Error getting imaged moment {imaged_moment_uuid}: {e}")
        raise e

    return response.json()


def get_image_reference(image_reference_uuid: str) -> dict:
    """
    Get an image reference by UUID.
    """
    LOGGER.debug(f"Getting image reference {image_reference_uuid}")
    response = m3.ANNOSAURUS_CLIENT.get_image_reference(image_reference_uuid)

    try:
        response.raise_for_status()
    except requests.exceptions.HTTPError as e:
        LOGGER.debug(f"Error getting image reference {image_reference_uuid}: {e}")
        raise e

    return response.json()


def get_video_sequence_names() -> List[str]:
    """
    Get a list of all video sequence names.
    """
    global VIDEO_SEQUENCE_NAMES
    if not VIDEO_SEQUENCE_NAMES:
        LOGGER.debug("Getting video sequence names from Vampire Squid")
        response = m3.VAMPIRE_SQUID_CLIENT.get_video_sequence_names()

        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            LOGGER.debug(f"Error getting video sequence names: {e}")
            raise e

        VIDEO_SEQUENCE_NAMES = response.json()
        LOGGER.debug(f"Got {len(VIDEO_SEQUENCE_NAMES)} video sequence names")

    return VIDEO_SEQUENCE_NAMES
