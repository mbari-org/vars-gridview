"""
M3 REST API clients.
"""

from collections.abc import Callable
from functools import wraps
from typing import Optional, ParamSpec, TypeVar, Concatenate
import requests
import requests.auth

from vars_gridview.lib.m3.query import QueryRequest


class JWTAuth(requests.auth.AuthBase):
    """
    JWT Auth class for requests.
    """

    def __init__(self, token: str):
        self._token = token

    def __call__(self, r):
        r.headers["Authorization"] = "BEARER {}".format(self._token)
        return r


class NotAuthenticated(Exception):
    """
    Raised when a client is not authenticated.
    """

    pass


P = ParamSpec("P")
R = TypeVar("R")


def needs_auth(
    f: Callable[Concatenate["M3Client", P], R],
) -> Callable[Concatenate["M3Client", P], R]:
    """
    Decorator to ensure that the client is authenticated.
    Raises NotAuthenticated if not.
    """

    @wraps(f)
    def wrapper(self: M3Client, *args: P.args, **kwargs: P.kwargs) -> R:
        if not self.authenticated:
            raise NotAuthenticated
        return f(self, *args, **kwargs)

    return wrapper


class M3Client:
    """
    M3 microservice client.
    """

    def __init__(self, base_url: str, api_key: str = None):
        self._session = requests.Session()

        self.base_url = base_url

        if api_key is not None:
            self.authenticate(api_key)

    @property
    def base_url(self) -> str:
        return self._base_url

    @base_url.setter
    def base_url(self, base_url: str):
        self._base_url = base_url.rstrip("/")

    def url_to(self, path: str) -> str:
        """
        Get the full URL for a path.
        """
        return self._base_url + path

    def get(self, path: str, **kwargs) -> requests.Response:
        return self._session.get(self.url_to(path), **kwargs)

    def put(self, path: str, **kwargs) -> requests.Response:
        return self._session.put(self.url_to(path), **kwargs)

    def post(self, path: str, **kwargs) -> requests.Response:
        return self._session.post(self.url_to(path), **kwargs)

    def delete(self, path: str, **kwargs) -> requests.Response:
        return self._session.delete(self.url_to(path), **kwargs)

    @property
    def authenticated(self) -> bool:
        """
        True if the client is authenticated.
        """
        return self._session.auth is not None

    def authenticate(self, api_key: str, auth_path: str = "/auth"):
        """
        Authenticate the client with the provided API key.
        """
        self._session.auth = None

        response = self.post(auth_path, headers={"Authorization": f"APIKEY {api_key}"})
        response.raise_for_status()

        token = response.json()["access_token"]
        self._session.auth = JWTAuth(token)


class AnnosaurusClient(M3Client):
    """
    Annosaurus (v1) client.
    """

    @needs_auth
    def create_association(self, data: dict) -> requests.Response:
        return self.post("/associations", data=data)

    @needs_auth
    def update_association(
        self, association_uuid: str, data: dict
    ) -> requests.Response:
        return self.put(f"/associations/{association_uuid}", data=data)

    @needs_auth
    def delete_association(self, association_uuid: str) -> requests.Response:
        return self.delete(f"/associations/{association_uuid}")

    def get_observation(self, observation_uuid: str) -> requests.Response:
        return self.get(f"/observations/{observation_uuid}")

    @needs_auth
    def create_observation(self, data: dict) -> requests.Response:
        return self.post("/annotations", data=data)

    @needs_auth
    def update_observation(
        self, observation_uuid: str, data: dict
    ) -> requests.Response:
        return self.put(f"/observations/{observation_uuid}", data=data)

    @needs_auth
    def delete_observation(self, observation_uuid: str) -> requests.Response:
        return self.delete(f"/observations/{observation_uuid}")

    def get_imaged_moment(self, imaged_moment_uuid: str) -> requests.Response:
        return self.get(f"/imagedmoments/{imaged_moment_uuid}")

    def get_image_reference(self, image_reference_uuid: str) -> requests.Response:
        return self.get(f"/imagereferences/{image_reference_uuid}")

    def query(self, query_request: QueryRequest) -> requests.Response:
        return self.post("/query/run", json=query_request.to_dict())

    def count(self, query_request: QueryRequest) -> requests.Response:
        return self.post("/query/count", json=query_request.to_dict())

    def query_download(self, query_request: QueryRequest) -> requests.Response:
        return self.post("/query/download", json=query_request.to_dict())


class VampireSquidClient(M3Client):
    """
    Vampire Squid (v1) client.
    """

    def get_videos_at_timestamp(self, timestamp: str) -> requests.Response:
        return self.get(f"/videos/timestamp/{timestamp}")

    def get_video_by_video_reference_uuid(
        self, video_reference_uuid: str
    ) -> requests.Response:
        return self.get(f"/videos/videoreference/{video_reference_uuid}")

    def get_video_sequence_names(self) -> requests.Response:
        return self.get("/videosequences/names")

    def get_video_sequence_by_name(self, name: str) -> requests.Response:
        return self.get(f"/videosequences/name/{name}")


class VARSUserServerClient(M3Client):
    """
    VARS user server (v1) client.
    """

    def url_to(self, path: str) -> str:
        return super().url_to(path)

    def get_all_users(self) -> requests.Response:
        return self.get("/users")


class VARSKBServerClient(M3Client):
    """
    VARS KB server (v1) client.
    """

    def get_concepts(self) -> requests.Response:
        return self.get("/concept")

    def get_concept(self, concept: str) -> requests.Response:
        return self.get(f"/concept/{concept}")

    def get_parts(self) -> requests.Response:
        return self.get("/phylogeny/taxa/organism part")

    def get_phylogeny_taxa(self, concept: str) -> requests.Response:
        return self.get(f"/phylogeny/taxa/{concept}")


class SkimmerClient(M3Client):
    """
    Skimmer client.
    """

    def crop(
        self,
        url: str,
        left: int,
        top: int,
        right: int,
        bottom: int,
        ms: Optional[int] = None,
    ) -> requests.Response:
        params = {
            "url": url,
            "left": left,
            "top": top,
            "right": right,
            "bottom": bottom,
        }
        if ms is not None:
            params["ms"] = ms
        return self.get("/crop", params=params)
