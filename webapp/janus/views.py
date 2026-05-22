import json
import re
from . import services
from .constants import Constants
from .forms import (
    ContainerProfileForm,
    NetworkProfileForm,
    VolumeProfileForm,
    SessionCreateForm,
)
from django.contrib.auth.models import User
from django.shortcuts import render, HttpResponseRedirect
from django.http import HttpResponseServerError, HttpResponseNotFound, JsonResponse
from django.urls import reverse


def _get_res_errors(data, res):
    try:
        sess = next(iter(res.values()))
    except Exception:
        return
    for k, v in sess.get("services").items():
        for srv in v:
            for err in srv.get("errors"):
                data["errors"].append(err)


def _get_user(request):
    user = User.objects.get(username=request.user)
    groups = list(user.groups.all())
    quser = user.username
    qgroups = [g.name for g in groups]
    if user.is_staff:
        quser = None
        qgroups = None
    return (user, groups, quser, qgroups)


def list_sessions(request, data=None):
    if not request.user.is_authenticated:
        return HttpResponseRedirect("/")

    if not data:
        data = {"errors": list()}
    (user, _, quser, qgroups) = _get_user(request)
    status, res = services.get_session_info(quser, qgroups)
    login = request.user.is_authenticated
    content = {
        "data": data,
        "user": user.username,
        "login": login,
        "is_admin": user.is_staff,
    }

    if status:
        content["sessions"] = res
    else:
        data["errors"].append(res)
    return render(request, "home.html", content)


def list_nodes(request):
    if not request.user.is_authenticated:
        return HttpResponseRedirect("/")

    (user, _, quser, qgroups) = _get_user(request)
    status, nodes = services.get_nodes(quser, qgroups, verbose=True)
    if status:
        content = {
            "nodes": nodes,
            "login": request.user.is_authenticated,
            "is_admin": user.is_staff,
        }
        return render(request, "node.html", content)
    else:
        return HttpResponseServerError()


def list_profiles(request, extra_content=dict(), refresh=False):
    if extra_content is None:
        extra_content = {}
    if not request.user.is_authenticated:
        return HttpResponseRedirect("/")
    (user, _, quser, qgroups) = _get_user(request)
    status, profiles = services.get_profiles(
        quser, qgroups, verbose=True, refresh=refresh
    )
    _, qos_choices = services.get_profiles(
        quser, qgroups, resource=Constants.QOS, verbose=True, refresh=refresh
    )
    _, net_choices = services.get_profiles(
        quser, qgroups, resource=Constants.NET, verbose=True, refresh=refresh
    )
    _, vol_choices = services.get_profiles(
        quser, qgroups, resource=Constants.VOL, verbose=True, refresh=refresh
    )
    kwargs = {
        Constants.QOS: [k.get("name") for k in qos_choices],
        Constants.NET: [k.get("name") for k in net_choices],
        Constants.VOL: [k.get("name") for k in vol_choices],
    }

    forms = dict()
    for p in profiles:
        forms.update(
            {f"{Constants.HOST}_{p['name']}": ContainerProfileForm(pfields=p, **kwargs)}
        )
    for p in net_choices:
        forms.update({f"{Constants.NET}_{p['name']}": NetworkProfileForm(nfields=p)})
    for p in vol_choices:
        forms.update({f"{Constants.VOL}_{p['name']}": VolumeProfileForm(vfields=p)})

    if status:
        content = {
            "profiles": profiles,
            "nets": net_choices,
            "vols": vol_choices,
            "login": request.user.is_authenticated,
            "is_admin": user.is_staff,
            "forms": forms,
        }
        content.update(extra_content)
        if "data" not in content:
            content["data"] = {"errors": []}
        return render(request, "profile.html", content)
    else:
        return HttpResponseServerError()


def refresh_profiles(request, extra_content=dict()):
    return list_profiles(request, extra_content, refresh=True)


def view_session(request, session_id):
    if request.user.is_authenticated:
        (user, _, quser, qgroups) = _get_user(request)
        status, sessions = services.get_session_info(
            quser, qgroups, session_id=session_id
        )
        if status and len(sessions) > 0:
            for key in sessions[0]:
                session_id = key
            content = {
                "session_d": key,
                "session": sessions[0][key],
                "login": request.user.is_authenticated,
                "is_admin": user.is_staff,
            }

            return render(request, "session_view.html", content)
        else:
            return HttpResponseNotFound()
    else:
        return HttpResponseRedirect("/")


def refresh_node(request):
    if not request.user.is_authenticated:
        return HttpResponseRedirect("/")

    (user, _, quser, qgroups) = _get_user(request)
    status, nodes = services.get_nodes(quser, qgroups, verbose=True, refresh=True)
    if status:
        content = {
            "nodes": nodes,
            "login": request.user.is_authenticated,
            "is_admin": user.is_staff,
        }
        return render(request, "node.html", content)
    else:
        return HttpResponseServerError()


def add_node(request):
    if not request.user.is_authenticated:
        return HttpResponseRedirect("/")

    (user, _, quser, qgroups) = _get_user(request)
    if user.is_staff:
        data = {"errors": list()}
        if request.method == "POST":
            name = request.POST.get("name", None)
            if name is not None and len(name):
                data["name"] = name
            else:
                data["errors"].append("Invalid name")
            url = request.POST.get("url", None)
            if url is not None and len(name):
                data["url"] = url
            else:
                data["errors"].append("Invalid URL")
            ntype = request.POST.get("ntype", None)
            if ntype is not None:
                data["type"] = int(ntype)

            # XXX use django Forms...
            if not len(data["errors"]):
                data["kwargs"] = {}
                status, res = services.add_node(data, quser, qgroups)
                if status:
                    return HttpResponseRedirect(reverse("janus:list_nodes"))
                else:
                    data["errors"].append(res)

        content = {
            "data": data,
            "ntypes": services.get_node_types(),
            "login": request.user.is_authenticated,
            "is_admin": user.is_staff,
        }
        return render(request, "add_node.html", content)
    else:
        return HttpResponseRedirect("/")


def remove_node(request, nname):
    if not request.user.is_authenticated:
        return HttpResponseRedirect("/")

    (user, _, quser, qgroups) = _get_user(request)
    status, _ = services.remove_node(nname, quser, qgroups)
    if status:
        return HttpResponseRedirect(reverse("janus:list_nodes"))
    else:
        return HttpResponseServerError()


def create_session(request):
    if not request.user.is_authenticated:
        return HttpResponseRedirect("/")

    (user, _, quser, qgroups) = _get_user(request)
    data = {"errors": list()}
    if request.method == "POST":
        node = request.POST.getlist("node", None)
        clusters = request.POST.getlist("clusters")
        if node is not None:
            if not clusters:
                data["instances"] = node
            else:
                instances = [
                    {"name": node_value, "nodeName": cluster_value}
                    for node_value, cluster_value in zip(node, clusters)
                ]
                data["instances"] = instances

        image = request.POST.get("image", None)
        if image is not None:
            data["image"] = image

        tag = request.POST.get("image_tag", "latest")
        if not tag:
            tag = "latest"
        data["image"] = data["image"] + f":{tag}"

        profile = request.POST.get("profile", "default")
        if profile is not None:
            data["profile"] = profile

        data["arguments"] = request.POST.get("arguments", None)

        data["kwargs"] = {}
        ssh_user_name = request.POST.get("ssh_user_name", None)
        if ssh_user_name is not None:
            data["kwargs"]["USER_NAME"] = ssh_user_name

        ssh_public_key = request.POST.get("ssh_public_key", None)
        if ssh_public_key is not None:
            data["kwargs"]["PUBLIC_KEY"] = ssh_public_key

        remove_container = request.POST.get("remove_container", None)
        data["remove_container"] = True if remove_container is not None else False

        # XXX use django Forms...
        if not len(data["errors"]):
            status, res = services.create_session(data, quser, qgroups)
            # look for errors for each created service
            errs = dict()
            if status and isinstance(res, dict):
                for sid, s in res.items():
                    if "services" in s:
                        for k, v in s["services"].items():
                            for n in v:
                                if len(n["errors"]):
                                    errs.update({k: n["errors"]})
            if status and not errs:
                return HttpResponseRedirect(reverse("janus:list_sessions"))
            else:
                data["errors"].append(errs if errs else res)

    _, nodes = services.get_nodes(quser, qgroups, verbose=True)
    _, profiles = services.get_profiles(quser, qgroups)
    _, images = services.get_images(quser, qgroups)
    clusters = {
        k["name"]: [node["name"] for node in k.get("data", {}).get("cluster_nodes", [])]
        for k in nodes
    }
    clusters_json = json.dumps(clusters)  # Serialize clusters data to JSON

    kwargs = {
        "nodes_list": [k.get("name") for k in nodes],
        "profiles_list": profiles,
        "images_list": [k.get("name") for k in images],
        "clusters": clusters,
    }

    forms = SessionCreateForm(sfields=None, **kwargs)
    content = {
        "data": data,
        "login": request.user.is_authenticated,
        "is_admin": user.is_staff,
        "forms": forms,
        "clusters": clusters_json,
    }

    return render(request, "session_create.html", content)


def update_profile(request, resource=Constants.HOST):
    def get_range(r, key):
        start = r.get(f"{key}_start")
        end = r.get(f"{key}_end")
        if not len(start) or not len(end):
            return None
        else:
            return [[int(start), int(end)]]

    def handle_host(request):
        pfields = dict()
        pfields["name"] = request.POST.get("name")
        s = dict()
        s["privileged"] = True if request.POST.get("privileged") else False
        s["systemd"] = True if request.POST.get("systemd") else False
        s["pull_image"] = True if request.POST.get("pull_image") else False
        s["cpu"] = (
            0 if not int(request.POST.get("cpu")) else int(request.POST.get("cpu"))
        )
        s["memory"] = (
            0
            if not int(request.POST.get("memory")) * 1024 * 1024 * 1024
            else int(request.POST.get("memory")) * 1024 * 1024 * 1024
        )
        s["mgmt_net"] = (
            None
            if request.POST.get("mgmt_net") == Constants.NONE
            else request.POST.get("mgmt_net")
        )
        s["data_net"] = (
            None
            if request.POST.get("data_net") == Constants.NONE
            else request.POST.get("data_net")
        )
        s["mgmt_net_ipv4"] = (
            None
            if not len(request.POST.get("mgmt_net_ipv4"))
            else request.POST.get("mgmt_net_ipv4")
        )
        s["mgmt_net_ipv6"] = (
            None
            if not len(request.POST.get("mgmt_net_ipv6"))
            else request.POST.get("mgmt_net_ipv6")
        )
        s["data_net_ipv4"] = (
            None
            if not len(request.POST.get("data_net_ipv4"))
            else request.POST.get("data_net_ipv4")
        )
        s["data_net_ipv6"] = (
            None
            if not len(request.POST.get("data_net_ipv6"))
            else request.POST.get("data_net_ipv6")
        )
        s["ctrl_ports"] = get_range(request.POST, "ctrl_ports")
        s["serv_ports"] = get_range(request.POST, "serv_ports")
        s["data_ports"] = get_range(request.POST, "data_ports")
        s["affinity"] = (
            None
            if not len(request.POST.get("affinity"))
            else request.POST.get("affinity")
        )
        s["arguments"] = (
            None
            if not len(request.POST.get("arguments"))
            else request.POST.get("arguments")
        )
        s["qos"] = (
            None
            if request.POST.get("qos") == Constants.NONE
            else request.POST.get("qos")
        )
        s["volumes"] = request.POST.getlist("volumes")
        env_str = request.POST.get("environment", "")
        valid_vars, env_errors = validate_environment_vars(env_str)
        if env_errors:
            data["errors"].extend(env_errors)
        else:
            s["environment"] = valid_vars
        pfields["settings"] = s
        return pfields

    def handle_net(request):
        pfields = dict()
        pfields["name"] = request.POST.get("name")
        s = dict()
        s["driver"] = (
            None if not len(request.POST.get("driver")) else request.POST.get("driver")
        )
        s["mode"] = (
            None if not len(request.POST.get("mode")) else request.POST.get("mode")
        )
        s["enable_ipv6"] = True if request.POST.get("enable_ipv6") else False
        s["ipam"] = None
        s["options"] = None
        subnet = (
            None
            if not len(request.POST.getlist("subnet"))
            else request.POST.getlist("subnet")
        )
        gateway = (
            None
            if not len(request.POST.getlist("gateway"))
            else request.POST.getlist("gateway")
        )
        opt_name = (
            None
            if not len(request.POST.getlist("opt_name"))
            else request.POST.getlist("opt_name")
        )
        opt_value = (
            None
            if not len(request.POST.getlist("opt_value"))
            else request.POST.getlist("opt_value")
        )
        if subnet:
            config = [
                {"subnet": subnet_val, "gateway": gateway_val}
                for subnet_val, gateway_val in zip(subnet, gateway)
            ]
            ipam = {"config": config}
            s["ipam"] = ipam

        if opt_name:
            options = {name: value for name, value in zip(opt_name, opt_value)}
            s["options"] = options

        pfields["settings"] = s
        return pfields

    def handle_vol(request):
        pfields = dict()
        pfields["name"] = request.POST.get("name")
        s = dict()
        s["type"] = (
            None if not len(request.POST.get("type")) else request.POST.get("type")
        )
        s["driver"] = (
            None if not len(request.POST.get("type")) else request.POST.get("driver")
        )
        s["source"] = (
            None if not len(request.POST.get("source")) else request.POST.get("source")
        )
        s["target"] = (
            None if not len(request.POST.get("target")) else request.POST.get("target")
        )
        pfields["settings"] = s
        return pfields

    if not request.user.is_authenticated:
        return HttpResponseRedirect("/")

    (user, _, quser, qgroups) = _get_user(request)

    if request.method == "POST":
        data = {"errors": list()}
        if resource == Constants.HOST:
            pfields = handle_host(request)
        elif resource == Constants.NET:
            pfields = handle_net(request)
        elif resource == Constants.VOL:
            pfields = handle_vol(request)

        content = {"data": data}

        if not data["errors"]:
            status, res = services.update_profile(resource, pfields, quser, qgroups)
            if status:
                return HttpResponseRedirect(reverse("janus:list_profiles"))
            else:
                data["errors"].append(res)
        return list_profiles(request, content)

    return HttpResponseRedirect(reverse("janus:list_profiles"))


def create_profile(request, resource=Constants.HOST):
    if not request.user.is_authenticated:
        return HttpResponseRedirect("/")
    (user, _, quser, qgroups) = _get_user(request)
    if user.is_staff:

        def get_range(r, key):
            start = r.get(f"{key}_start")
            end = r.get(f"{key}_end")
            if not start or not end or not len(start) or not len(end):
                return None
            else:
                return [[int(start), int(end)]]

        data = {"errors": list()}
        name = request.POST.get("name", None)
        if resource == Constants.HOST:
            if request.method == "POST":
                if not name:
                    data["errors"].append("Invalid name")

                data["privileged"] = request.POST.get("privileged", "default")
                data["systemd"] = request.POST.get("systemd", "default")
                data["pull_image"] = request.POST.get("pull_image", "default")
                for opt in ["privileged", "systemd", "pull_image"]:
                    data[opt] = True if data[opt] == "on" else False

                data["cpu"] = request.POST.get("cpu", 0)
                if not data["cpu"]:
                    data["cpu"] = 0
                data["cpu"] = int(data["cpu"])

                data["memory"] = request.POST.get("memory", 0)
                if not data["memory"]:
                    data["memory"] = 0
                data["memory"] = int(data["memory"]) * 1024 * 1024 * 1024

                mgmt_net = dict()
                mgmt_net_name = request.POST.get("mgmt_net")
                if mgmt_net_name == Constants.NONE:
                    mgmt_net_name = None
                mgmt_net_ipv4 = (
                    None
                    if not len(request.POST.get("mgmt_net_ipv4"))
                    else request.POST.get("mgmt_net_ipv4")
                )
                mgmt_net_ipv6 = (
                    None
                    if not len(request.POST.get("mgmt_net_ipv6"))
                    else request.POST.get("mgmt_net_ipv6")
                )
                mgmt_net.update({"name": mgmt_net_name})
                mgmt_net.update({"ipv4_addr": mgmt_net_ipv4})
                mgmt_net.update({"ipv6_addr": mgmt_net_ipv6})
                data["mgmt_net"] = mgmt_net

                data_net = dict()
                data_net_name = request.POST.get("data_net")
                if data_net_name == Constants.NONE:
                    data_net_name = None
                data_net_ipv4 = (
                    None
                    if not len(request.POST.get("data_net_ipv4"))
                    else request.POST.get("data_net_ipv4")
                )
                data_net_ipv6 = (
                    None
                    if not len(request.POST.get("data_net_ipv6"))
                    else request.POST.get("data_net_ipv6")
                )
                data_net.update({"name": data_net_name})
                data_net.update({"ipv4_addr": data_net_ipv4})
                data_net.update({"ipv6_addr": data_net_ipv6})
                data["data_net"] = data_net

                data["internal_port"] = request.POST.get("internal_port", None)
                if not data["internal_port"]:
                    data["internal_port"] = None
                data["internal_port"] = (
                    int(data["internal_port"]) if data["internal_port"] else None
                )

                data["ctrl_ports"] = get_range(request.POST, "ctrl_ports")
                data["data_ports"] = get_range(request.POST, "data_ports")
                data["serv_ports"] = get_range(request.POST, "serv_ports")

                data["affinity"] = (
                    "network"
                    if not len(request.POST.get("affinity"))
                    else request.POST.get("affinity")
                )

                data["arguments"] = (
                    None
                    if not len(request.POST.get("arguments"))
                    else request.POST.get("arguments")
                )

                data["volumes"] = request.POST.getlist("volumes", None)

                data["qos"] = request.POST.get("qos", None)
                if data["qos"] == Constants.NONE:
                    data["qos"] = None

                env_str = request.POST.get("environment", "")
                valid_vars, env_errors = validate_environment_vars(env_str)
                if env_errors:
                    data["errors"].extend(env_errors)
                else:
                    data["environment"] = valid_vars

                profile = {"name": name, "settings": data}

                # XXX use django Forms...
                if not len(data["errors"]):
                    status, res = services.create_profile(
                        resource, profile, quser, qgroups
                    )
                    if status:
                        return HttpResponseRedirect(reverse("janus:list_profiles"))
                    else:
                        data["errors"].append(res)

            _, qos_choices = services.get_profiles(
                quser, qgroups, resource=Constants.QOS, verbose=True
            )
            _, vol_choices = services.get_profiles(
                quser, qgroups, resource=Constants.VOL, verbose=True
            )
            _, net_choices = services.get_profiles(
                quser, qgroups, resource=Constants.NET, verbose=True
            )
            kwargs = {
                Constants.QOS: [k.get("name") for k in qos_choices],
                Constants.NET: [k.get("name") for k in net_choices],
                Constants.VOL: [k.get("name") for k in vol_choices],
            }

            forms = ContainerProfileForm(pfields=None, **kwargs)
            content = {
                "data": data,
                "login": request.user.is_authenticated,
                "is_admin": user.is_staff,
                "forms": forms,
            }
            return render(request, "profile_create.html", content)

        elif resource == Constants.VOL:
            if request.method == "POST":
                if not name:
                    data["errors"].append("Invalid name")
                data["type"] = request.POST.get("type", None)
                data["source"] = (
                    None
                    if not len(request.POST.get("source"))
                    else request.POST.get("source")
                )
                data["target"] = (
                    None
                    if not len(request.POST.get("target"))
                    else request.POST.get("target")
                )
                data["driver"] = (
                    None
                    if not len(request.POST.get("driver"))
                    else request.POST.get("driver")
                )

                volume = {"name": name, "settings": data}

                if not len(data["errors"]):
                    status, res = services.create_profile(
                        resource, volume, quser, qgroups
                    )
                    if status:
                        return HttpResponseRedirect(reverse("janus:list_profiles"))
                    else:
                        data["errors"].append(res)

            forms = VolumeProfileForm(vfields=None)
            content = {
                "data": data,
                "login": request.user.is_authenticated,
                "is_admin": user.is_staff,
                "forms": forms,
            }
            return render(request, "create_volume.html", content)

        elif resource == Constants.NET:
            if request.method == "POST":
                if not name:
                    data["errors"].append("Invalid name")
                data["driver"] = request.POST.get("driver", None)
                data["mode"] = (
                    None
                    if not len(request.POST.get("mode"))
                    else request.POST.get("mode")
                )
                data["enable_ipv6"] = True if request.POST.get("enable_ipv6") else False

                data["ipam"] = None
                subnet = request.POST.getlist("subnet", None)
                gateway = request.POST.getlist("gateway", None)
                if subnet[0]:
                    config = [
                        {"subnet": subnet_val, "gateway": gateway_val}
                        for subnet_val, gateway_val in zip(subnet, gateway)
                    ]
                    ipam = {"config": config}
                    data["ipam"] = ipam

                data["options"] = None
                opts = request.POST.getlist("opt_name", None)
                opts_values = request.POST.getlist("opt_value", None)
                if len(opts) != 0:
                    options = {name: value for name, value in zip(opts, opts_values)}
                    data["options"] = options

                network = {"name": name, "settings": data}

                if not len(data["errors"]):
                    status, res = services.create_profile(
                        resource, network, quser, qgroups
                    )
                    if status:
                        return HttpResponseRedirect(reverse("janus:list_profiles"))
                    else:
                        data["errors"].append(res)

            forms = NetworkProfileForm(nfields=None)
            content = {
                "data": data,
                "login": request.user.is_authenticated,
                "is_admin": user.is_staff,
                "forms": forms,
            }
            return render(request, "create_network.html", content)

    else:
        return HttpResponseRedirect("/")


def start_session(request, session_id):
    if request.user.is_authenticated:
        data = {"errors": list()}
        (user, _, quser, qgroups) = _get_user(request)
        status, res = services.start_session(session_id, quser, qgroups)
        if status:
            _get_res_errors(data, res)
            if data["errors"]:
                return list_sessions(request, data)
            else:
                return HttpResponseRedirect("/")
    else:
        return HttpResponseRedirect("/")


def stop_session(request, session_id):
    if request.user.is_authenticated:
        data = {"errors": list()}
        (user, _, quser, qgroups) = _get_user(request)
        status, res = services.stop_session(session_id, quser, qgroups)
        if status:
            _get_res_errors(data, res)
            if data["errors"]:
                return list_sessions(request, data)
            else:
                return HttpResponseRedirect("/")
    else:
        return HttpResponseRedirect("/")


def delete_session(request, session_id):
    if request.user.is_authenticated:
        data = {"errors": list()}
        (user, _, quser, qgroups) = _get_user(request)
        status, res = services.delete_session(session_id, quser, qgroups)
        if status:
            _get_res_errors(data, res)
            if data["errors"]:
                return list_sessions(request, data)
            else:
                return HttpResponseRedirect("/")
    else:
        return HttpResponseRedirect("/")


def delete_profile(request, pname, resource=Constants.HOST):
    if request.user.is_authenticated:
        (user, _, quser, qgroups) = _get_user(request)
        status, _ = services.delete_profile(resource, pname, quser, qgroups)
        if status:
            return HttpResponseRedirect(reverse("janus:list_profiles"))
        else:
            return HttpResponseServerError()
    else:
        return HttpResponseRedirect("/")


# Non-template response views
def create_session_api(request):
    if not request.user.is_authenticated:
        return JsonResponse({"error": "Unauthorized"}, status=401)
    if request.method == "POST":
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON"}, status=400)

        (user, _, quser, qgroups) = _get_user(request)
        
        # Add tag to image if not present
        if "image" in data and ":" not in data["image"]:
            data["image"] = data["image"] + ":latest"
            
        status, res = services.create_session(data, quser, qgroups)
        return JsonResponse({"status": status, "result": res}, status=200 if status else 400)
    return JsonResponse({"error": "Method not allowed"}, status=405)


def get_sessions_api(request):
    if not request.user.is_authenticated:
        return JsonResponse({"error": "Unauthorized"}, status=401)
    (user, _, quser, qgroups) = _get_user(request)
    status, res = services.get_session_info(quser, qgroups)
    if status:
        return JsonResponse({"sessions": res})
    else:
        return JsonResponse({"error": res}, status=500)


def start_session_api(request, session_id):
    if not request.user.is_authenticated:
        return JsonResponse({"error": "Unauthorized"}, status=401)
    (user, _, quser, qgroups) = _get_user(request)
    status, res = services.start_session(session_id, quser, qgroups)
    return JsonResponse({"status": status, "result": res}, status=200 if status else 400)


def stop_session_api(request, session_id):
    if not request.user.is_authenticated:
        return JsonResponse({"error": "Unauthorized"}, status=401)
    (user, _, quser, qgroups) = _get_user(request)
    status, res = services.stop_session(session_id, quser, qgroups)
    return JsonResponse({"status": status, "result": res}, status=200 if status else 400)


def delete_session_api(request, session_id):
    if not request.user.is_authenticated:
        return JsonResponse({"error": "Unauthorized"}, status=401)
    (user, _, quser, qgroups) = _get_user(request)
    status, res = services.delete_session(session_id, quser, qgroups)
    return JsonResponse({"status": status, "result": res}, status=200 if status else 400)


def get_nodes_api(request):
    if not request.user.is_authenticated:
        return JsonResponse({"error": "Unauthorized"}, status=401)
    (user, _, quser, qgroups) = _get_user(request)
    refresh = request.GET.get("refresh") == "true"
    status, nodes = services.get_nodes(quser, qgroups, verbose=True, refresh=refresh)
    if status:
        return JsonResponse({"nodes": nodes})
    else:
        return JsonResponse({"error": "Could not fetch nodes"}, status=500)


def add_node_api(request):
    if not request.user.is_authenticated or not request.user.is_staff:
        return JsonResponse({"error": "Unauthorized"}, status=401)
    if request.method == "POST":
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON"}, status=400)

        (user, _, quser, qgroups) = _get_user(request)
        status, res = services.add_node(data, quser, qgroups)
        return JsonResponse({"status": status, "result": res}, status=200 if status else 400)
    return JsonResponse({"error": "Method not allowed"}, status=405)


def remove_node_api(request, nname):
    if not request.user.is_authenticated or not request.user.is_staff:
        return JsonResponse({"error": "Unauthorized"}, status=401)
    (user, _, quser, qgroups) = _get_user(request)
    status, res = services.remove_node(nname, quser, qgroups)
    return JsonResponse({"status": status, "result": res}, status=200 if status else 400)


def view_log(request, session_id, nname):
    if not request.user.is_authenticated:
        return JsonResponse({"error": "Unauthorized"}, status=401)
    ts = request.GET.get("timestamps")
    (status, log) = services.get_log(session_id, nname, ts)
    if status:
        return JsonResponse(log)
    else:
        return JsonResponse({"error": "Could not find logs"})


def validate_environment_vars(env_str):
    errors = []
    valid_vars = []
    for i, line in enumerate(env_str.splitlines(), start=1):
        line = line.strip()
        if not line:
            continue
        if line.count("=") != 1:
            if "=" not in line:
                errors.append(f"Line {i}: Missing '=' operator in environment variable")
            else:
                errors.append(
                    f"Line {i}: Multiple '=' operator detected in environment variable"
                )
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key:
            errors.append(f"Line {i}: Empty environment variable name before '='")
            continue
        if not re.match(r"^[A-Z_][A-Z0-9_]*$", key, re.I):
            errors.append(
                f"Line {i}: Invalid environment variable name format '{key}'. Must start with letter/underscore and contain only alphanumerics/underscores"
            )
            continue
        valid_vars.append(f"{key}={value.strip()}")
    return valid_vars, errors



def get_images_api(request):
    if not request.user.is_authenticated:
        return JsonResponse({"error": "Unauthorized"}, status=401)
    (user, _, quser, qgroups) = _get_user(request)
    status, images = services.get_images(quser, qgroups)
    if status:
        return JsonResponse({"images": images})
    else:
        return JsonResponse({"error": "Could not fetch images"}, status=500)


def get_profiles_api(request, resource="host"):
    if not request.user.is_authenticated:
        return JsonResponse({"error": "Unauthorized"}, status=401)
    (user, _, quser, qgroups) = _get_user(request)
    refresh = request.GET.get("refresh") == "true"
    status, profiles = services.get_profiles(
        quser, qgroups, verbose=True, resource=resource, refresh=refresh
    )
    if status:
        return JsonResponse({"profiles": profiles})
    else:
        return JsonResponse({"error": "Could not fetch profiles"}, status=500)


def get_node_types_api(request):
    if not request.user.is_authenticated:
        return JsonResponse({"error": "Unauthorized"}, status=401)
    ntypes = services.get_node_types()
    return JsonResponse(ntypes)


def get_profile_choices_api(request):
    if not request.user.is_authenticated:
        return JsonResponse({"error": "Unauthorized"}, status=401)
    (user, _, quser, qgroups) = _get_user(request)
    _, qos = services.get_profiles(quser, qgroups, resource=Constants.QOS, verbose=True)
    _, nets = services.get_profiles(
        quser, qgroups, resource=Constants.NET, verbose=True
    )
    _, vols = services.get_profiles(
        quser, qgroups, resource=Constants.VOL, verbose=True
    )
    return JsonResponse(
        {
            "qos": [k.get("name") for k in qos],
            "networks": [k.get("name") for k in nets],
            "volumes": [k.get("name") for k in vols],
        }
    )


def create_profile_api(request, resource):
    if not request.user.is_authenticated or not request.user.is_staff:
        return JsonResponse({"error": "Unauthorized"}, status=401)
    if request.method == "POST":
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON"}, status=400)
        (user, _, quser, qgroups) = _get_user(request)
        status, res = services.create_profile(resource, data, quser, qgroups)
        return JsonResponse(
            {"status": status, "result": res}, status=200 if status else 400
        )
    return JsonResponse({"error": "Method not allowed"}, status=405)


def update_profile_api(request, resource):
    if not request.user.is_authenticated:
        return JsonResponse({"error": "Unauthorized"}, status=401)
    if request.method == "POST":
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON"}, status=400)
        (user, _, quser, qgroups) = _get_user(request)
        status, res = services.update_profile(resource, data, quser, qgroups)
        return JsonResponse(
            {"status": status, "result": res}, status=200 if status else 400
        )
    return JsonResponse({"error": "Method not allowed"}, status=405)


def delete_profile_api(request, resource, pname):
    if not request.user.is_authenticated:
        return JsonResponse({"error": "Unauthorized"}, status=401)
    (user, _, quser, qgroups) = _get_user(request)
    status, res = services.delete_profile(resource, pname, quser, qgroups)
    return JsonResponse(
        {"status": status, "result": res}, status=200 if status else 400
    )

def update_session_api(request, session_id):
    if not request.user.is_authenticated:
        return JsonResponse({"error": "Unauthorized"}, status=401)
    if request.method == "POST":
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON"}, status=400)

        (user, _, quser, qgroups) = _get_user(request)
        apply = request.GET.get("apply") == "true"
        
        # Add tag to image if not present
        if "image" in data and ":" not in data["image"]:
            data["image"] = data["image"] + ":latest"

        status, res = services.update_session(session_id, data, quser, qgroups, apply)
        return JsonResponse({"status": status, "result": res}, status=200 if status else 400)
    return JsonResponse({"error": "Method not allowed"}, status=405)


def apply_session_changes_api(request, session_id):
    if not request.user.is_authenticated:
        return JsonResponse({"error": "Unauthorized"}, status=401)
    (user, _, quser, qgroups) = _get_user(request)
    status, res = services.apply_session_changes(session_id, quser, qgroups)
    return JsonResponse({"status": status, "result": res}, status=200 if status else 400)
