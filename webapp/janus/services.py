# Session management API call to Janus Controller

import math
import requests
from django.conf import settings

base_url = settings.JANUS_CONTROLLER_URL + "api/janus/controller/"


def convert_size(size_bytes):
    if size_bytes == 0:
        return "0B"
    size_name = ("B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB")
    i = int(math.floor(math.log(size_bytes, 1024)))
    p = math.pow(1024, i)
    s = round(size_bytes / p)
    return "%s %s" % (s, size_name[i])

def get_node_types():
    ntypes = {1: "1: Portainer Agent",
              2: "2: Docker",
              3: "3: Kubernetes"}
    return ntypes

def add_node(data, user=None, groups=None):
    res = requests.post(
        url=base_url + "nodes",
        json=data,
        auth=settings.JANUS_CONTROLLER_AUTH,
        verify=settings.CTRL_SSL_VERIFY
    )
    status, data = False, []
    if res.status_code in [200, 204]:
        status = True
    else:
        status = False
        data = res.json()
    return status, data

def remove_node(nname, user=None, groups=None):
    res = requests.delete(
        url=base_url + f"nodes/{nname}",
        auth=settings.JANUS_CONTROLLER_AUTH,
        verify=settings.CTRL_SSL_VERIFY
    )
    status, data = False, []
    if res.status_code in [200, 204]:
        status = True
    else:
        status = False
        data = res.json()
    return status, data

def get_session_info(user=None, groups=None, session_id=None):
    """
    Get session info from Janus Controller
    :param session_id int:
    :param name str:
    :return:
    """
    url = base_url + "active"
    if session_id is not None:
        url += f"/{session_id}"
    elif user is not None:
        url += f"?user={user}"

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
                if not entry:
                    continue
                temp = {
                    "id": entry["id"],
                    "user": entry["user"],
                    "state": entry["state"],
                    "image": entry["request"][0]["image"],
                    "profile": entry["request"][0]["profile"],
                    "nodes": [s for s in entry["services"].keys()]
                }
                data.append(temp)

    return status, data

def create_session(data, user=None, groups=None):
    """
    Create session on Janus Controller
    :param data dict:
    :return:
    """
    url = base_url + "create"
    if user:
        url += f"?user={user}"
    res = requests.post(
        url=base_url + "create",
        json=data,
        auth=settings.JANUS_CONTROLLER_AUTH,
        verify=settings.CTRL_SSL_VERIFY
    )

    if res.status_code == 200:
        return True, res.json()
    else:
        return False, res.json()


def start_session(session_id, user=None, groups=None):
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


def stop_session(session_id, user=None, groups=None):
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


def delete_session(session_id, user=None, groups=None):
    """
    Delete session on Janus Controller
    :param session_id int:
    :return:
    """
    res = requests.delete(
        url=base_url + "active/" + str(session_id) + "?force=true",
        auth=settings.JANUS_CONTROLLER_AUTH,
        verify=settings.CTRL_SSL_VERIFY
    )

    if res.status_code == 204:
        return True, {}
    else:
        return False, {}


def get_profiles(user=None, groups=None, verbose=False, pname=None):
    """
    Get profiles list from Janus Controller
    :return:
    """
    profile_url = base_url + f"profiles"
    if pname:
        profile_url += f"/{pname}"
    if user:
        profile_url += f"?user={user}"

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
                    profiles.append(entry)
                else:
                    profiles.append(entry["name"])

    return (status, profiles)


def create_profile(data, user=None, groups=None):
    """
    Create profile on Janus Controller
    :param data dict:
    :return:
    """
    name = data["name"]
    res = requests.post(
        url=base_url + f"profiles/{name}",
        json=data,
        auth=settings.JANUS_CONTROLLER_AUTH,
        verify=settings.CTRL_SSL_VERIFY
    )

    if res.status_code == 200:
        return True, res.json()
    else:
        return False, res.json()


def delete_profile(pname, user=None, groups=None):
    """ Delete profile from Janus Controller """
    res = requests.delete(
        url=base_url + f"profiles/{pname}",
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
        temp["id"] = node["id"] if "id" in node else None
        temp["status"] = node["endpoint_status"] if "endpoint_status" in node else None
        temp["name"] = node["name"] if "name" in node else None
        temp["url"] = node["url"] if "url" in node else None
        temp["cpu_model"] = node["host"]["cpu"]["brand_raw"] if "host" in node else None
        temp["cpu_core"] = node["host"]["cpu"]["count"] if "host" in node else None
        temp["memory"] = node["host"]["mem"]["total"] if "host" in node else None
        temp["memory_str"] = convert_size(temp['memory']) if "memory" in node else None
        temp["image"] = len(node["images"]) if "images" in node else None
        temp["networks"] = len(node["networks"]) if "networks" in node else None
        nodes_list.append(temp)

    return nodes_list


def get_nodes(user=None, groups=None, verbose=False, nname=None):
    """
    Get nodes list from Janus Controller
    :return:
    """
    url = "nodes" if nname is None else "nodes/" + nname
    if user:
        url += f"?user={user}"
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


def get_images(nname, user=None, groups=None):
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
        images = res.json()["images"]

    return (status, images)

def get_qos():
    """
    Get QoS list from Janus Controller
    :return:
    """
    res = requests.get(
        url = base_url + "qos",
        auth=settings.JANUS_CONTROLLER_AUTH,
        verify=settings.CTRL_SSL_VERIFY
    )

    status, qos = False, []
    if res.status_code == 200:
        status = True
        qos = list(res.json().keys())

    return (status, qos)
