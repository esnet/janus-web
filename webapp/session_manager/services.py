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
        if session_id is not None:
            data = res.json()
        else:
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


def get_profiles(verbose=False, pname=None):
    """
    Get profiles list from Janus Controller
    :return:
    """
    profile_url = base_url + "profiles"
    if pname:
        profile_url += "?pname=" + pname

    res = requests.get(
        url = profile_url,
        auth=settings.JANUS_CONTROLLER_AUTH,
        verify=settings.CTRL_SSL_VERIFY
    )

    status, profiles = False, []
    if res.status_code == 200:
        status = True
        if pname:
            profiles = res.json()
        else:
            for entry in res.json():
                if verbose:
                    temp = res.json()[entry]
                    temp["pname"] = entry
                    profiles.append(temp)
                else:
                    profiles.append(entry)

    return (status, profiles)


def delete_profile(pname):
    """ Delete profile from Janus Controller """
    res = requests.delete(
        url=base_url + "profiles",
        json={"name": pname},
        auth=settings.JANUS_CONTROLLER_AUTH,
        verify=settings.CTRL_SSL_VERIFY
    )

    if res.status_code == 204:
        return True, {}
    else:
        return False, {}


def process_nodes(nodes):
    """
    Process nodes list to get only the name of the nodes
    :param nodes list:
    :return:
    """
    nodes_list = []
    for node in nodes:
        temp = {}
        temp["name"] = node["name"] if "name" in node else None
        temp["url"] = node["url"] if "url" in node else None
        temp["cpu_model"] = node["host"]["cpu"]["brand_raw"] if "host" in node else None
        temp["cpu_core"] = node["host"]["cpu"]["count"] if "host" in node else None
        temp["memory"] = node["host"]["mem"]["total"] if "host" in node else None
        temp["image"] = len(node["images"]) if "images" in node else 0
        temp["networks"] = len(node["networks"]) if "networks" in node else 0
        nodes_list.append(temp)

    return nodes_list


def get_nodes(verbose=False, nname=None):
    """
    Get nodes list from Janus Controller
    :return:
    """
    url = "nodes" if nname is None else "nodes/" + nname
    res = requests.get(
        url = base_url+url,
        auth=settings.JANUS_CONTROLLER_AUTH,
        verify=settings.CTRL_SSL_VERIFY
    )

    status, nodes = False, []

    if res.status_code == 200:
        status = True
        if verbose:
            nodes = process_nodes(res.json())
        else:
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
