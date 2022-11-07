import requests
import logging
from django.conf import settings

logger = logging.getLogger(__name__)
base_url = settings.JANUS_CONTROLLER_URL + "api/janus/controller/"

def set_access(resource, data):
    logger.debug(f"set_access: {resource} {data}")
    if resource == "nodes":
        rname = data["node"]
    elif resource == "images":
        rname = data["image"]
    elif resource == "profiles":
        rname = data["profile"]
    else:
        return False, "Invalid resource"

    post_body = {
        "users": data["users"],
        "groups": data["groups"]
    }
    res = requests.post(
        url=base_url + f"auth/{resource}/{rname}",
        json=post_body,
        auth=settings.JANUS_CONTROLLER_AUTH,
        verify=settings.CTRL_SSL_VERIFY
    )

    if res.status_code == 200:
        return True, res.json()
    else:
        return False, res.json()


