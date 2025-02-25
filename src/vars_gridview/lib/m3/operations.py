"""
M3 operations. Make use of the clients defined in __init__.py.
"""

import json
from typing import Dict, Iterable, List, Optional

import requests

from vars_gridview.lib import m3
from vars_gridview.lib.log import LOGGER
from vars_gridview.lib.m3.query import QueryRequest
from vars_gridview.lib.utils import parse_tsv

KB_CONCEPTS: Dict[str, Optional[str]] = None
KB_PARTS: List[str] = None
USERS = None
VIDEO_SEQUENCE_NAMES = None


def get_kb_concepts() -> Dict[str, Optional[str]]:
    """
    Get a list of all concepts in the KB.

    Returns:
        Dict[str, Optional[str]]: Dictionary of concepts mapped to their common names. If the name is not cached, it is None.

    Raises:
        requests.exceptions.HTTPError: If the request fails.
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

    Args:
        concept (str): The concept to get the name for.

    Returns:
        Optional[str]: The name of the concept.

    Raises:
        requests.exceptions.HTTPError: If the request fails.
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

    Returns:
        List[str]: List of part names.

    Raises:
        requests.exceptions.HTTPError: If the request fails.
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

    Args:
        concept (str): The concept to get the descendants for.

    Returns:
        List[str]: List of descendant names.

    Raises:
        requests.exceptions.HTTPError: If the request fails.
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

    Returns:
        List[dict]: List of user data dicts.

    Raises:
        requests.exceptions.HTTPError: If the request fails.
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

    Args:
        association_uuid (str): UUID of the association to update.
        box_dict (dict): The bounding box data.

    Returns:
        dict: The updated association data.

    Raises:
        requests.exceptions.HTTPError: If the request fails.
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

    Args:
        association_uuid (str): UUID of the association to update.
        part (str): The part to set.

    Returns:
        dict: The updated association data.

    Raises:
        requests.exceptions.HTTPError: If the request fails.
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

    Args:
        observation_uuid (str): UUID of the observation to update.
        concept (str): The concept to set.
        observer (str): The observer to set.

    Returns:
        dict: The updated observation data.

    Raises:
        requests.exceptions.HTTPError: If the request fails.
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


def delete_association(association_uuid: str) -> None:
    """
    Delete an association.

    Args:
        association_uuid (str): UUID of the association to delete.

    Raises:
        requests.exceptions.HTTPError: If the request fails.
    """
    LOGGER.debug(f"Deleting association {association_uuid}")
    response = m3.ANNOSAURUS_CLIENT.delete_association(association_uuid)

    try:
        response.raise_for_status()
    except requests.exceptions.HTTPError as e:
        LOGGER.debug(f"Error deleting association {association_uuid}: {e}")
        raise e


def get_observation(observation_uuid: str) -> dict:
    """
    Get an observation by UUID.

    Args:
        observation_uuid (str): The observation UUID.

    Returns:
        dict: The observation data.

    Raises:
        requests.exceptions.HTTPError: If the request fails.
    """
    LOGGER.debug(f"Getting observation {observation_uuid}")
    response = m3.ANNOSAURUS_CLIENT.get_observation(observation_uuid)

    try:
        response.raise_for_status()
    except requests.exceptions.HTTPError as e:
        LOGGER.debug(f"Error getting observation {observation_uuid}: {e}")
        raise e

    return response.json()


def delete_observation(observation_uuid: str) -> None:
    """
    Delete an observation.

    Args:
        observation_uuid (str): UUID of the observation to delete.

    Raises:
        requests.exceptions.HTTPError: If the request fails.
    """
    LOGGER.debug(f"Deleting observation {observation_uuid}")
    response = m3.ANNOSAURUS_CLIENT.delete_observation(observation_uuid)

    try:
        response.raise_for_status()
    except requests.exceptions.HTTPError as e:
        LOGGER.debug(f"Error deleting observation {observation_uuid}: {e}")
        raise e


def get_video_sequence_by_name(name: str) -> dict:
    """
    Get a video sequence by name.

    Args:
        name (str): The video sequence name.

    Returns:
        dict: The video sequence data.

    Raises:
        requests.exceptions.HTTPError: If the request fails.
    """
    LOGGER.debug(f"Getting video sequence by name {name}")
    response = m3.VAMPIRE_SQUID_CLIENT.get_video_sequence_by_name(name)

    try:
        response.raise_for_status()
    except requests.exceptions.HTTPError as e:
        LOGGER.debug(f"Error getting video sequence by name {name}: {e}")
        raise e

    return response.json()


def get_image_reference(image_reference_uuid: str) -> dict:
    """
    Get an image reference by UUID.

    Args:
        image_reference_uuid (str): The image reference UUID.

    Returns:
        dict: The image reference data.

    Raises:
        requests.exceptions.HTTPError: If the request fails.
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

    Returns:
        List[str]: List of video sequence names.

    Raises:
        requests.exceptions.HTTPError: If the request fails.
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


def query(query_request: QueryRequest) -> str:
    """
    Query the M3 API.

    Args:
        query_request (QueryRequest): The query request.

    Returns:
        str: The response text.

    Raises:
        requests.exceptions.HTTPError: If the query fails.
    """
    LOGGER.debug("Querying Annosaurus")
    response = m3.ANNOSAURUS_CLIENT.query(query_request)

    try:
        response.raise_for_status()
    except requests.exceptions.HTTPError as e:
        LOGGER.debug(f"Error during query: {e}")
        raise e

    return response.text


def query_paged(
    query_request: QueryRequest, page_size: int = 5000
) -> Iterable[List[str]]:
    """
    Query the M3 API, paginating the requests.

    Args:
        query_request (QueryRequest): The query request.
        page_size (int): The number of results to request per page.

    Yields:
        Iterable[List[str]]: Generator of result row lists. The first row is the header.

    Raises:
        requests.exceptions.HTTPError: If the query fails.
    """
    request = QueryRequest(**query_request.to_dict())
    request.limit = page_size
    request.offset = 0

    headers_yielded = False
    while True:
        LOGGER.debug(
            f"Querying Annosaurus with offset {request.offset} and limit {request.limit}"
        )
        response = query(request)
        headers, rows = parse_tsv(response)

        if not headers_yielded:
            yield headers
            headers_yielded = True

        yield from rows

        request.offset += page_size
        if len(rows) < page_size:
            break


def query_download(query_request: QueryRequest) -> str:
    """
    Query the M3 API using the download endpoint.

    Args:
        query_request (QueryRequest): The query request.

    Returns:
        str: The response text.

    Raises:
        requests.exceptions.HTTPError: If the query fails.
    """
    LOGGER.debug("Querying Annosaurus (download)")
    response = m3.ANNOSAURUS_CLIENT.query_download(query_request)

    try:
        response.raise_for_status()
    except requests.exceptions.HTTPError as e:
        LOGGER.debug(f"Error during query: {e}")
        raise e

    return response.text


def crop(
    url: str, left: int, top: int, right: int, bottom: int, ms: Optional[int] = None
) -> requests.Response:
    """
    Crop an image or video using Skimmer.

    Args:
        url (str): URL of the image or video.
        left (int): Left crop coordinate.
        top (int): Top crop coordinate.
        right (int): Right crop coordinate.
        bottom (int): Bottom crop coordinate.
        ms (Optional[int]): Millisecond to crop for videos.

    Returns:
        requests.Response: The response object.

    Raises:
        requests.exceptions.HTTPError: If the request fails.
    """
    timestamp_str = f" at {ms} ms" if ms is not None else ""
    LOGGER.debug(f"Cropping {url}{timestamp_str} to {left}, {top}, {right}, {bottom}")
    response = m3.SKIMMER_CLIENT.crop(url, left, top, right, bottom, ms)

    try:
        response.raise_for_status()
    except requests.exceptions.HTTPError as e:
        LOGGER.debug(f"Error cropping {url}: {e}")
        raise e

    return response
