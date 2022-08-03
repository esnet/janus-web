# Session management API call to Janus Controller

import requests
from django.conf import settings

base_url = settings.JANUS_CONTROLLER_URL + "api/janus/controller/"


def get_session_info(name=None, session_id=None):
    """
    Get session info from Janus Controller
    :param session_id int:
    :param name str:
    :return:
    """
    url = base_url + "active"
    if session_id is not None:
        url += "/" + str(session_id)

    elif name is not None:
        url += "/" + name

    res = requests.get(
        url = url,
        auth=settings.JANUS_CONTROLLER_AUTH,
        verify=settings.CTRL_SSL_VERIFY
    )

    status, data = False, []
    if res.status_code == 200:
        status = True
        for entry in res.json():
            for key in entry:
                temp = {
                    "id": key,
                    "user": entry[key]["user"],
                    "state": entry[key]["state"]
                }
                data.append(temp)

    return status, data


def create_session(data):
    """
    Create session on Janus Controller
    :param data dict:
    :return:
    """
    res = requests.post(
        url=base_url + "create",
        json=data,
        auth=settings.JANUS_CONTROLLER_AUTH,
        verify=settings.CTRL_SSL_VERIFY
    )

    if res.status_code == 200:
        return True, res.json()
    else:
        return False, {}


def start_session(session_id):
    """
    Start session on Janus Controller
    :param session_id int:
    :return:
    """
    res = requests.put(
        url=base_url + "start/" + str(session_id),
        auth=settings.JANUS_CONTROLLER_AUTH,
        verify=settings.CTRL_SSL_VERIFY
    )

    if res.status_code == 200:
        return True, res.json()
    else:
        return False, {}


def stop_session(session_id):
    """
    Stop session on Janus Controller
    :param session_id int:
    :return:
    """
    res = requests.put(
        url=base_url + "stop/" + str(session_id),
        auth=settings.JANUS_CONTROLLER_AUTH,
        verify=settings.CTRL_SSL_VERIFY
    )

    if res.status_code == 200:
        return True, res.json()
    else:
        return False, {}


def delete_session(session_id):
    """
    Delete session on Janus Controller
    :param session_id int:
    :return:
    """
    res = requests.delete(
        url=base_url + "active/" + str(session_id),
        auth=settings.JANUS_CONTROLLER_AUTH,
        verify=settings.CTRL_SSL_VERIFY
    )

    if res.status_code == 204:
        return True, {}
    else:
        return False, {}


def get_profiles():
    """
    Get profiles list from Janus Controller
    :return:
    """
    res = requests.get(
        url = base_url + "profiles",
        auth=settings.JANUS_CONTROLLER_AUTH,
        verify=settings.CTRL_SSL_VERIFY
    )

    status, profiles = False, []
    if res.status_code == 200:
        status = True
        for entry in res.json():
            profiles.append(entry)

    return (status, profiles)


def get_nodes():
    """
    Get nodes list from Janus Controller
    :return:
    """
    res = requests.get(
        url = base_url + "nodes",
        auth=settings.JANUS_CONTROLLER_AUTH,
        verify=settings.CTRL_SSL_VERIFY
    )

    status, nodes = False, []

    if res.status_code == 200:
        status = True
        for entry in res.json():
            nodes.append(entry['name'])

    return (status, nodes)


def get_images(nname):
    """
    Get nodes list from Janus Controller
    :return:
    """
    res = requests.get(
        url = base_url + "nodes/" + nname,
        auth=settings.JANUS_CONTROLLER_AUTH,
        verify=settings.CTRL_SSL_VERIFY
    )

    status, images = False, []
    if res.status_code == 200:
        images = res.json()[0]["images"]

    return (status, images)
