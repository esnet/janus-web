import requests
import logging
from django.conf import settings

logger = logging.getLogger(__name__)
base_url = settings.JANUS_CONTROLLER_URL + "api/janus/controller/"

def set_access(resource, data, remove=False):
    logger.debug(f"set_access: {resource} {data}")
    if resource == "nodes":
        identifier = data["node"]
    elif resource == "images":
        identifier = data["image"]
    elif resource == "profiles":
        identifier = data["profile"]
    elif resource == "active":
        identifier = data["session_id"]
    else:
        return False, "Invalid resource"

    post_body = {
        "users": data["users"],
        "groups": data["groups"]
    }

    fn = requests.delete if remove else requests.post
    res = fn(
        url=base_url + f"auth/{resource}/{identifier}",
        json=post_body,
        auth=settings.JANUS_CONTROLLER_AUTH,
        verify=settings.CTRL_SSL_VERIFY
    )

    if res.status_code == 200:
        return True, res.json()
    else:
        return False, res.json()


