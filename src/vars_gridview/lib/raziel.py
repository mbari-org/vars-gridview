from base64 import b64encode

import requests


def authenticate(url: str, username: str, password: str):
    """
    Authenticate with Raziel and get the endpoint information.
    """
    # Encode the username and password
    user_pass_base64 = "Basic " + b64encode(
        "{}:{}".format(username, password).encode("utf-8")
    ).decode("utf-8")

    # Attempt to authenticate with Raziel
    res = requests.post(url + "/auth", headers={"Authorization": user_pass_base64})
    res.raise_for_status()

    # Get the token from the response
    token = res.json()["accessToken"]

    # Get the endpoints from Raziel
    return requests.get(
        url + "/endpoints", headers={"Authorization": "Bearer " + token}
    ).json()
