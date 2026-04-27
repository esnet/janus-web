# Session management API call to Janus Controller

import httpx
import shlex
from django.conf import settings
from .utils import convert_size
from .constants import Constants


base_url = settings.JANUS_CONTROLLER_URL + "api/janus/controller/"


def get_node_types():
    ntypes = {1: "1: Portainer Agent", 2: "2: Kubernetes", 3: "3: Docker", 4: "4: Slurm"}
    return ntypes


def add_node(data, user=None, groups=None):
    params = get_params(user, groups)
    res = httpx.post(
        url=base_url + "nodes",
        json=data,
        auth=settings.JANUS_CONTROLLER_AUTH,
        verify=settings.CTRL_SSL_VERIFY,
        params=params,
    )
    if res.status_code in [200, 201, 204]:
        try:
            return True, res.json() if res.status_code != 204 else {}
        except Exception:
            return True, {}
    else:
        return False, res.json()


def remove_node(nname, user=None, groups=None):
    res = httpx.delete(
        url=base_url + f"nodes/{nname}",
        auth=settings.JANUS_CONTROLLER_AUTH,
        verify=settings.CTRL_SSL_VERIFY,
    )
    if res.status_code in [200, 204]:
        return True, {}
    else:
        try:
            return False, res.json()
        except Exception:
            return False, {"error": res.text or f"HTTP {res.status_code}"}


def get_auth_jwt():
    res = httpx.get(
        url=f"{base_url}auth/jwt",
        auth=settings.JANUS_CONTROLLER_AUTH,
        verify=settings.CTRL_SSL_VERIFY,
    )

    status, data = False, []
    if res.status_code == 200:
        status = True
        data = res.json().get("jwt", None)
    return status, data


def create_exec(nid, cid, cmd, start=True, attach=True, tty=False):
    data = {
        "node": nid,
        "container": cid,
        "Cmd": shlex.split(cmd),
        "attach": attach,
        "tty": tty,
        "start": start,
    }

    res = httpx.post(
        url=f"{base_url}exec",
        json=data,
        auth=settings.JANUS_CONTROLLER_AUTH,
        verify=settings.CTRL_SSL_VERIFY,
    )
    status, data = False, []
    if res.status_code in [200, 204]:
        status = True
        data = res.json().get("Id", None)
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

    # also get profile info
    params = get_params(user, groups)
    res = httpx.get(
        url=f"{base_url}profiles",
        auth=settings.JANUS_CONTROLLER_AUTH,
        verify=settings.CTRL_SSL_VERIFY,
        params=params,
    )
    if res.status_code == 200:
        data = res.json()
        profiles = dict()
        for p in data:
            profiles.update({p["name"]: p})
    else:
        profiles = None

    res = httpx.get(
        url=url,
        auth=settings.JANUS_CONTROLLER_AUTH,
        verify=settings.CTRL_SSL_VERIFY,
        params=params,
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
                prof = entry["request"][0]["profile"]
                img = entry["request"][0]["image"]
                simg = img.split(":")[0]
                tools = list()
                if profiles:
                    try:
                        tools = profiles[prof]["settings"]["tools"].get(simg, list())
                    except Exception:
                        pass
                if not entry:
                    continue
                temp = {
                    "id": entry["id"],
                    "user": entry["user"],
                    "state": entry["state"],
                    "image": img,
                    "profile": prof,
                    "nodes": [s for s in entry["services"].keys()],
                    "tools": tools,
                    "data": entry,
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
    params = get_params(user, groups)
    res = httpx.post(
        url=url,
        json=data,
        auth=settings.JANUS_CONTROLLER_AUTH,
        verify=settings.CTRL_SSL_VERIFY,
        params=params,
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
    res = httpx.put(
        url=base_url + "start/" + str(session_id),
        auth=settings.JANUS_CONTROLLER_AUTH,
        verify=settings.CTRL_SSL_VERIFY,
    )

    if res.status_code == 200:
        return True, res.json()
    else:
        return False, res.json()


def stop_session(session_id, user=None, groups=None):
    """
    Stop session on Janus Controller
    :param session_id int:
    :return:
    """
    res = httpx.put(
        url=base_url + "stop/" + str(session_id),
        auth=settings.JANUS_CONTROLLER_AUTH,
        verify=settings.CTRL_SSL_VERIFY,
    )

    if res.status_code == 200:
        return True, res.json()
    else:
        return False, res.json()


def delete_session(session_id, user=None, groups=None):
    """
    Delete session on Janus Controller
    :param session_id int:
    :return:
    """
    res = httpx.delete(
        url=base_url + "active/" + str(session_id) + "?force=true",
        auth=settings.JANUS_CONTROLLER_AUTH,
        verify=settings.CTRL_SSL_VERIFY,
    )

    if res.status_code == 204:
        return True, {}
    else:
        return False, res.json()


def get_profiles(
    user=None, groups=None, verbose=False, resource="host", pname=None, refresh=False
):
    """
    Get profiles list from Janus Controller
    :return:
    """
    profile_url = base_url + f"profiles/{resource}"
    if pname:
        profile_url += f"/{pname}"
    params = get_params(user, groups, refresh)

    res = httpx.get(
        url=profile_url,
        auth=settings.JANUS_CONTROLLER_AUTH,
        verify=settings.CTRL_SSL_VERIFY,
        params=params,
    )

    status, profiles = False, []
    if res.status_code == 200:
        status = True
        if pname:
            entry = res.json()
            if not entry.get("settings"):
                entry["settings"] = dict()
            else:
                s = entry["settings"]
                for k in ["mgmt_net", "data_net"]:
                    if k in s and isinstance(s[k], dict):
                        s[f"{k}_ipv4"] = s[k].get("ipv4_addr")
                        s[f"{k}_ipv6"] = s[k].get("ipv6_addr")
                        s[k] = s[k].get("name")
            profiles = entry
        else:
            for entry in res.json():
                if verbose:
                    if not entry.get("settings"):
                        entry["settings"] = dict()
                    else:
                        # Extract nested network info for legacy UI compatibility if needed
                        # but keep the rest as-is for round-tripping
                        s = entry["settings"]
                        for k in ["mgmt_net", "data_net"]:
                            if k in s and isinstance(s[k], dict):
                                s[f"{k}_ipv4"] = s[k].get("ipv4_addr")
                                s[f"{k}_ipv6"] = s[k].get("ipv6_addr")
                                s[k] = s[k].get("name")
                    profiles.append(entry)
                else:
                    profiles.append(entry["name"])

    return (status, profiles)


def create_profile(resource, data, user=None, groups=None):
    """
    Create profile on Janus Controller
    :param data dict:
    :return:
    """
    name = data["name"]
    params = get_params(user, groups)
    res = httpx.post(
        url=base_url + f"profiles/{resource}/{name}",
        json=data,
        auth=settings.JANUS_CONTROLLER_AUTH,
        verify=settings.CTRL_SSL_VERIFY,
        params=params,
    )
    if res.status_code == 200:
        return True, res.json()
    else:
        return False, res.json()


def update_profile(resource, data, user=None, groups=None):
    """
    Update profile on Janus Controller
    :param data dict:
    :return:
    """
    name = data.get("name")
    s = data.get("settings")
    # Convert networks into fully-specified dict syntax
    if resource == Constants.HOST:
        for k in ["mgmt_net", "data_net"]:
            if k in s:
                # If it's already a dict, we might not need to do anything
                # but let's ensure the legacy fields are handled safely
                if not isinstance(s[k], dict):
                    s[k] = {
                        "name": s.get(k),
                        "ipv4_addr": s.get(f"{k}_ipv4"),
                        "ipv6_addr": s.get(f"{k}_ipv6"),
                    }
                # Safely remove legacy keys if they exist
                s.pop(f"{k}_ipv4", None)
                s.pop(f"{k}_ipv6", None)
    res = httpx.put(
        url=base_url + f"profiles/{resource}/{name}",
        json=data,
        auth=settings.JANUS_CONTROLLER_AUTH,
        verify=settings.CTRL_SSL_VERIFY,
    )

    if res.status_code == 200:
        return True, res.json()
    else:
        try:
            return False, res.json()
        except Exception:
            return False, {"error": res.text or f"HTTP {res.status_code}"}


def delete_profile(resource, pname, user=None, groups=None):
    """Delete profile from Janus Controller"""
    res = httpx.delete(
        url=base_url + f"profiles/{resource}/{pname}",
        auth=settings.JANUS_CONTROLLER_AUTH,
        verify=settings.CTRL_SSL_VERIFY,
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
        temp["memory_str"] = convert_size(temp["memory"]) if "host" in node else None
        temp["image"] = len(node["images"]) if "images" in node else None
        temp["networks"] = len(node["networks"]) if "networks" in node else None
        temp["data"] = node
        nodes_list.append(temp)

    return nodes_list


def get_nodes(user=None, groups=None, verbose=False, nname=None, refresh=False):
    """
    Get nodes list from Janus Controller
    :return:
    """
    url = "nodes" if nname is None else "nodes/" + nname
    params = get_params(user, groups, refresh)
    res = httpx.get(
        url=base_url + url,
        auth=settings.JANUS_CONTROLLER_AUTH,
        verify=settings.CTRL_SSL_VERIFY,
        params=params,
        timeout=30.0,
    )

    status, nodes = False, []

    if res.status_code == 200:
        status = True
        if verbose:
            nodes = process_nodes(res.json())
        else:
            for entry in res.json():
                nodes.append(entry["name"])

    return (status, nodes)


def get_images(user=None, groups=None, iname=None):
    """
    Get nodes list from Janus Controller
    :return:
    """
    url = f"{base_url}images"
    if iname:
        url += f"/{iname}"
    params = get_params(user, groups)
    res = httpx.get(
        url=url,
        auth=settings.JANUS_CONTROLLER_AUTH,
        verify=settings.CTRL_SSL_VERIFY,
        params=params,
    )

    status, images = False, []
    if res.status_code == 200:
        images = res.json()
        status = True

    return (status, images)


def get_qos():
    """
    Get QoS list from Janus Controller
    :return:
    """
    res = httpx.get(
        url=base_url + "qos",
        auth=settings.JANUS_CONTROLLER_AUTH,
        verify=settings.CTRL_SSL_VERIFY,
    )

    status, qos = False, []
    if res.status_code == 200:
        status = True
        qos = list(res.json().keys())

    return (status, qos)


def get_log(sid, nname, timestamps=0):
    """
    Get container logs from Janus Controller
    :return:
    """
    params = dict()
    params["timestamps"] = timestamps
    url = f"{base_url}active/{sid}/logs/{nname}"
    res = httpx.get(
        url=url,
        auth=settings.JANUS_CONTROLLER_AUTH,
        verify=settings.CTRL_SSL_VERIFY,
        params=params,
    )
    status, log = False, dict()
    if res.status_code == 200:
        status = True
        log = res.json()
    return (status, log)


def get_params(user=None, groups=None, refresh=False, timestamps=0):
    params = dict()
    if user:
        params["user"] = user
    if groups:
        params["group"] = ",".join(groups)
    if refresh:
        params["refresh"] = "true"
    if timestamps:
        params["timestamps"] = timestamps
    return params
