"""
M3 client wrapper.
"""

import json
from datetime import datetime
from typing import Dict, List, Optional

import requests
from beholder_client import BeholderClient

from vars_gridview.lib import raziel
from vars_gridview.lib.log import LOGGER
from vars_gridview.lib.m3.clients import (
    AnnosaurusClient,
    M3Client,
    VampireSquidClient,
    VARSKBServerClient,
    VARSUserServerClient,
)


def reauth(client: M3Client):
    """
    Decorator factory to reauthenticate an M3 client and retry if a request fails due to an expired token.

    Works by intercepting a requests.exceptions.HTTPError with status code 401.

    Args:
        client: The M3 client to reauthenticate. Assumes the API key has already been set.

    Returns:
        A decorator that reauthenticates the client and retries the request if it fails due to an expired token.
    """

    def decorator(f):
        def wrapper(*args, **kwargs):
            try:
                return f(*args, **kwargs)
            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 401:
                    LOGGER.debug(f"Reauthenticating due to error 401: {e}")
                    client.authenticate()
                    return f(*args, **kwargs)
                else:
                    raise e

        return wrapper

    return decorator


def raise_for_status(response: requests.Response, debug_msg: Optional[str] = None):
    """
    Raise an exception if the given response has an error status code. Optionally log a debug message.

    Args:
        response: The response to check.
        debug_msg: Optional debug message to log if the response has an error status code.

    Raises:
        requests.exceptions.HTTPError: If the response has an error status code.
    """
    try:
        response.raise_for_status()
    except requests.exceptions.HTTPError as e:
        LOGGER.debug(f"{debug_msg}: {e}")
        raise e


class M3ClientWrapper:
    """
    Client wrapper for M3 operations.

    Encapsulates the M3 clients and provides methods for common operations.
    """

    def __init__(
        self,
        annosaurus_client: AnnosaurusClient,
        vampire_squid_client: VampireSquidClient,
        vars_user_server_client: VARSUserServerClient,
        vars_kb_server_client: VARSKBServerClient,
        beholder_client: BeholderClient,
    ):
        # Clients
        self._anno = annosaurus_client
        self._vam = vampire_squid_client
        self._users = vars_user_server_client
        self._kb = vars_kb_server_client
        self._beholder = beholder_client

        # Cached data
        self._kb_concept_map: Optional[
            Dict[str, Optional[str]]
        ] = None  # concept -> name (or None if not yet fetched)
        self._kb_parts: Optional[List[str]] = None
        self._users_data: Optional[List[dict]] = None
        self._video_sequence_names: Optional[List[str]] = None

        # Decorate methods that might fail due to an expired token
        self._decorate_reauthentication()

    @classmethod
    def from_raziel(cls, raziel_url: str, username: str, password: str):
        """
        Create and authenticate an M3Client from a Raziel (configuration service) instance.

        Args:
            raziel_url: URL of the Raziel instance.
            username: Username to authenticate with.
            password: Password to authenticate with.

        Returns:
            The M3Client with authenticated service clients.

        Raises:
            ValueError: If the Raziel instance does not contain the required endpoints.
        """
        LOGGER.debug(f"Creating M3 client from Raziel instance {raziel_url}")
        endpoints = raziel.authenticate(raziel_url, username, password)

        def get_client_url_secret(name: str):
            data = next((e for e in endpoints if e["name"] == name), None)
            if data is None:
                raise ValueError(f'Endpoint "{name}" not found')
            return data["url"], data["secret"]

        # Create the clients
        anno_url, anno_api_key = get_client_url_secret("annosaurus")
        annosaurus_client = AnnosaurusClient(anno_url)
        annosaurus_client.authenticate(anno_api_key)
        LOGGER.debug(f"Configured and authenticated Annosaurus client at {anno_url}")

        vam_url, _ = get_client_url_secret("vampire-squid")
        vampire_squid_client = VampireSquidClient(vam_url)
        LOGGER.debug(f"Configured Vampire Squid client at {vam_url}")

        users_url, _ = get_client_url_secret("vars-user-server")
        vars_user_server_client = VARSUserServerClient(users_url)
        LOGGER.debug(f"Configured VARS User Server client at {users_url}")

        kb_url, _ = get_client_url_secret("vars-kb-server")
        vars_kb_server_client = VARSKBServerClient(kb_url)
        LOGGER.debug(f"Configured VARS KB Server client at {kb_url}")

        beholder_url, beholder_api_key = get_client_url_secret("beholder")
        beholder_client = BeholderClient(beholder_url, beholder_api_key)
        LOGGER.debug(f"Configured and authenticated Beholder client at {beholder_url}")

        return cls(
            annosaurus_client,
            vampire_squid_client,
            vars_user_server_client,
            vars_kb_server_client,
            beholder_client,
        )

    def _decorate_reauthentication(self):
        """
        Apply the reauthentication decorator to all methods that make requests that might fail due to an expired token.
        """
        self.update_bounding_box_data = reauth(self._anno)(
            self.update_bounding_box_data
        )
        self.update_bounding_box_part = reauth(self._anno)(
            self.update_bounding_box_part
        )
        self.update_observation_concept = reauth(self._anno)(
            self.update_observation_concept
        )
        self.create_association = reauth(self._anno)(self.create_association)
        self.delete_association = reauth(self._anno)(self.delete_association)
        self.get_observation = reauth(self._anno)(self.get_observation)
        self.create_observation = reauth(self._anno)(self.create_observation)
        self.delete_observation = reauth(self._anno)(self.delete_observation)

    @property
    def kb_concept_map(self) -> Dict[str, Optional[str]]:
        """
        The map of all concepts in the KB to their names.
        """
        if self._kb_concept_map is None:
            self._init_kb_concept_map()

        return self._kb_concept_map

    @property
    def kb_concepts(self) -> List[str]:
        """
        The list of all concepts in the KB.
        """
        return list(self.kb_concept_map.keys())

    @property
    def kb_parts(self) -> List[str]:
        """
        The list of all parts in the KB.
        """
        if self._kb_parts is None:
            self._init_kb_parts()

        return self._kb_parts

    @property
    def users_data(self) -> List[dict]:
        """
        The list of all users as dicts.
        """
        if self._users_data is None:
            self._init_users_data()

        return self._users_data

    @property
    def video_sequence_names(self) -> List[str]:
        """
        The list of all video sequence names.
        """
        if self._video_sequence_names is None:
            self._init_video_sequence_names()

        return self._video_sequence_names

    def _init_kb_concept_map(self):
        """
        Initialize the KB concept map.
        """
        LOGGER.debug("Getting concepts from KB")

        response = self._kb.get_concepts()
        raise_for_status(response, "Error getting concepts from KB")

        concept_names = response.json()
        self._kb_concept_map = {concept: None for concept in concept_names}
        LOGGER.debug(f"Got {len(self._kb_concept_map)} concepts from KB")

    def _init_kb_parts(self):
        """
        Initialize the KB parts list.
        """
        LOGGER.debug("Getting parts from KB")

        response = self._kb.get_parts()
        raise_for_status(response, "Error getting parts from KB")

        self._kb_parts = [part["name"] for part in response.json()]
        LOGGER.debug(f"Got {len(self._kb_parts)} parts from KB")

    def _init_users_data(self):
        """
        Initialize the users data.
        """
        LOGGER.debug("Getting users from VARS user server")

        response = self._users.get_all_users()
        raise_for_status(response, "Error getting users from VARS user server")

        self._users_data = response.json()
        LOGGER.debug(f"Got {len(self._users_data)} users from VARS user server")

    def _init_video_sequence_names(self):
        """
        Initialize the video sequence names list.
        """
        LOGGER.debug("Getting video sequence names from Vampire Squid")
        response = self._vam.get_video_sequence_names()
        raise_for_status(response, "Error getting video sequence names")

        self._video_sequence_names = response.json()
        LOGGER.debug(f"Got {len(self._video_sequence_names)} video sequence names")

    def get_kb_name(self, concept: str) -> Optional[str]:
        """
        Get the name of a concept in the KB. Uses the cached KB concept map.

        Args:
            concept: The concept to get the name of.

        Returns:
            The name of the concept, or None if the concept does not exist.
        """
        concept_map = self.kb_concept_map

        if concept_map.get(concept, None) is None:  # not yet fetched
            # Get the concept data from the KB
            response = self._kb.get_concept(concept)
            raise_for_status(
                response, f"Error getting concept name for {concept} from KB"
            )

            name = response.json().get("name")
            LOGGER.debug(f"Got name {name} for concept {concept} from KB")

            # Update the concept map with the name
            concept_map[concept] = name

        return concept_map[concept]

    def get_kb_descendants(self, concept: str) -> List[str]:
        """
        Get a list of all descendants of a concept in the KB, including the concept.

        Args:
            concept: The concept to get the descendants of.

        Returns:
            A list of all descendants of the concept, including the concept.
        """
        LOGGER.debug(f"Getting descendants of {concept} from KB")
        response = self._kb.get_phylogeny_taxa(concept)

        if response.status_code == 404:
            return []  # concept not found, so no descendants
        else:
            raise_for_status(
                response, f"Error getting descendants of {concept} from KB"
            )

        parsed_response = response.json()
        taxa_names = [taxa["name"] for taxa in parsed_response]
        LOGGER.debug(f"Got {len(taxa_names)} descendants of {concept} from KB")
        return taxa_names

    def update_bounding_box_data(self, association_uuid: str, box_dict: dict) -> dict:
        """
        Update a bounding box association's JSON data (`link_value`).

        Args:
            association_uuid: UUID of the association to update.
            box_dict: The new bounding box data.

        Returns:
            The updated bounding box association data.
        """
        request_data = {
            "link_value": json.dumps(box_dict),
        }

        LOGGER.debug(
            f"Updating bounding box data for {association_uuid}:\n{request_data}"
        )
        response = self._anno.update_association(association_uuid, request_data)
        raise_for_status(
            response, f"Error updating bounding box data for {association_uuid}"
        )

        return response.json()

    def update_bounding_box_part(self, association_uuid: str, part: str) -> dict:
        """
        Update a bounding box association's part (`to_concept`).

        Args:
            association_uuid: UUID of the association to update.
            part: The new part. Should be a valid part in the KB (see `kb_parts`).

        Returns:
            The updated bounding box association data.
        """
        request_data = {
            "to_concept": part,
        }

        LOGGER.debug(
            f"Updating bounding box part for {association_uuid}:\n{request_data}"
        )
        response = self._anno.update_association(association_uuid, request_data)
        raise_for_status(
            response, f"Error updating bounding box part for {association_uuid}"
        )

        return response.json()

    def update_observation_concept(
        self, observation_uuid: str, concept: str, observer: str
    ) -> dict:
        """
        Update an observation's concept and observer.

        Args:
            observation_uuid: UUID of the observation to update.
            concept: The new concept. Should be a valid concept in the KB (see `kb_concepts`).
            observer: The new observer. Should be a valid username (see `users_data`).

        Returns:
            The updated observation data.
        """
        request_data = {
            "concept": concept,
            "observer": observer,  # when we update the concept, we also update the observer
        }

        LOGGER.debug(
            f"Updating observation concept for {observation_uuid}:\n{request_data}"
        )
        response = self._anno.update_observation(observation_uuid, request_data)
        raise_for_status(
            response, f"Error updating observation concept for {observation_uuid}"
        )

        return response.json()

    def create_association(self, association: dict) -> requests.Response:
        """
        Create an association.

        Args:
            association: The association to create.

        Returns:
            The response from the server.
        """
        LOGGER.debug(f"Creating association:\n{association}")
        response = self._anno.create_association(association)
        raise_for_status(response, "Error creating association")

        return response

    def delete_association(self, association_uuid: str) -> requests.Response:
        """
        Delete an association.

        Args:
            association_uuid: UUID of the association to delete.

        Returns:
            The response from the server.
        """
        LOGGER.debug(f"Deleting association {association_uuid}")
        response = self._anno.delete_association(association_uuid)
        raise_for_status(response, f"Error deleting association {association_uuid}")

        return response

    def get_observation(self, observation_uuid: str) -> dict:
        """
        Get an observation by UUID.

        Args:
            observation_uuid: UUID of the observation to get.

        Returns:
            The observation data.
        """
        LOGGER.debug(f"Getting observation {observation_uuid}")
        response = self._anno.get_observation(observation_uuid)
        raise_for_status(response, f"Error getting observation {observation_uuid}")

        return response.json()

    def create_observation(self, observation: dict) -> requests.Response:
        """
        Create an observation.

        Args:
            observation: The observation to create.

        Returns:
            The response from the server.
        """
        LOGGER.debug(f"Creating observation:\n{observation}")
        response = self._anno.create_observation(observation)
        raise_for_status(response, "Error creating observation")

        return response

    def delete_observation(self, observation_uuid: str) -> requests.Response:
        """
        Delete an observation.

        Args:
            observation_uuid: UUID of the observation to delete.

        Returns:
            The response from the server.
        """
        LOGGER.debug(f"Deleting observation {observation_uuid}")
        response = self._anno.delete_observation(observation_uuid)
        raise_for_status(response, f"Error deleting observation {observation_uuid}")

        return response

    def get_videos_at_datetime(self, dt: datetime) -> List[dict]:
        """
        Get a list of videos occurring at a given instant.

        Args:
            dt: The datetime to get videos at.

        Returns:
            A list of video data for all videos occurring at the given datetime.
        """
        timestamp = dt.strftime("%Y-%m-%dT%H:%M:%S.%fZ")

        LOGGER.debug(f"Getting videos at {timestamp}")
        response = self._vam.get_videos_at_timestamp(timestamp)
        raise_for_status(response, f"Error getting videos at {timestamp}")

        return response.json()

    def get_video_by_video_reference_uuid(self, video_reference_uuid: str) -> dict:
        """
        Get a video's information by a contained video reference UUID.

        Args:
            video_reference_uuid: UUID of the video reference contained in the video.

        Returns:
            The corresponding video data.
        """
        LOGGER.debug(f"Getting video by video reference UUID {video_reference_uuid}")
        response = self._vam.get_video_by_video_reference_uuid(video_reference_uuid)
        raise_for_status(
            response,
            f"Error getting video by video reference UUID {video_reference_uuid}",
        )

        return response.json()

    def get_video_sequence_by_name(self, name: str) -> dict:
        """
        Get a video sequence by name.

        Note: this operation is slow (typically 1-2 seconds), so its results should be cached.
        Future work will be done to optimize this endpoint on the server side.

        Args:
            name: The name of the video sequence.

        Returns:
            The video sequence data.
        """
        LOGGER.debug(f"Getting video sequence by name {name}")
        response = self._vam.get_video_sequence_by_name(name)
        raise_for_status(response, f"Error getting video sequence by name {name}")

        return response.json()

    def get_imaged_moment(self, imaged_moment_uuid: str) -> dict:
        """
        Get an imaged moment by UUID.

        Args:
            imaged_moment_uuid: UUID of the imaged moment to get.

        Returns:
            The imaged moment data.
        """
        LOGGER.debug(f"Getting imaged moment {imaged_moment_uuid}")
        response = self._anno.get_imaged_moment(imaged_moment_uuid)
        raise_for_status(response, f"Error getting imaged moment {imaged_moment_uuid}")

        return response.json()

    def get_image_reference(self, image_reference_uuid: str) -> dict:
        """
        Get an image reference by UUID.
        """
        LOGGER.debug(f"Getting image reference {image_reference_uuid}")
        response = self._anno.get_image_reference(image_reference_uuid)
        raise_for_status(
            response, f"Error getting image reference {image_reference_uuid}"
        )

        return response.json()

    def capture_raw(self, video_url: str, elapsed_time_millis: int) -> bytes:
        """
        Capture a raw image from a video at a given number of milliseconds into the video.

        Args:
            video_url: URL of the video to capture from.
            elapsed_time_millis: Number of milliseconds into the video to capture from.

        Returns:
            The response from the server.
        """
        LOGGER.debug(
            f"Capturing via Beholder from {video_url} at {elapsed_time_millis}ms"
        )
        image_bytes = self._beholder.capture_raw(video_url, elapsed_time_millis)

        return image_bytes
