import logging
from . import services
from .constants import Constants
from .forms import *
from django.contrib.auth.models import User
from django.shortcuts import render, HttpResponseRedirect
from django.http import HttpResponseServerError, HttpResponseNotFound, JsonResponse
from django.urls import reverse

logger = logging.getLogger(__name__)

def _get_res_errors(data, res):
    try:
        sess = next(iter(res.values()))
    except Exception as e:
        return
    for k,v in sess.get('services').items():
        for srv in v:
            for err in srv.get('errors'):
                data['errors'].append(err)

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
        return HttpResponseRedirect('/')

    if not data:
        data = {"errors": list()}
    (user,_,quser,qgroups) = _get_user(request)
    status, res = services.get_session_info(quser, qgroups)
    login = request.user.is_authenticated
    content = {
        'data': data,
        'user': user.username,
        'login': login,
        'is_admin': user.is_staff,
    }

    if status:
        content['sessions'] = res
    else:
        data['errors'].append(res)

    return render(request, 'home.html', content)


def list_nodes(request):
    if not request.user.is_authenticated:
        return HttpResponseRedirect('/')

    (user,_,quser,qgroups) = _get_user(request)
    status, nodes = services.get_nodes(quser, qgroups, verbose=True)
    if status:
        content = {
            'nodes': nodes,
            'login': request.user.is_authenticated,
            'is_admin': user.is_staff
        }
        return render(request, 'node.html', content)
    else:
        return HttpResponseServerError()

def list_profiles(request, extra_content=dict(), refresh=False):
    if not request.user.is_authenticated:
        return HttpResponseRedirect('/')
    (user,_,quser,qgroups) = _get_user(request)
    status, profiles = services.get_profiles(quser, qgroups, verbose=True, refresh=refresh)
    _, qos_choices = services.get_profiles(quser, qgroups, resource=Constants.QOS, verbose=True, refresh=refresh)
    _, net_choices = services.get_profiles(quser, qgroups, resource=Constants.NET, verbose=True, refresh=refresh)
    _, vol_choices = services.get_profiles(quser, qgroups, resource=Constants.VOL, verbose=True, refresh=refresh)
    kwargs = {Constants.QOS: [k.get('name') for k in qos_choices],
              Constants.NET: [k.get('name') for k in net_choices],
              Constants.VOL: [k.get('name') for k in vol_choices]}

    forms = dict()
    for p in profiles:
        forms.update({f"{Constants.HOST}_{p['name']}": ContainerProfileForm(pfields=p, **kwargs)})
    for p in net_choices:
        forms.update({f"{Constants.NET}_{p['name']}": NetworkProfileForm(nfields=p)})
    for p in vol_choices:
        forms.update({f"{Constants.VOL}_{p['name']}": VolumeProfileForm(vfields=p)})

    if status:
        content = {
            "profiles": profiles,
            "nets": net_choices,
            "vols": vol_choices,
            'login': request.user.is_authenticated,
            'is_admin': user.is_staff,
            'forms': forms
        }
        content.update(extra_content)
        return render(request, 'profile.html', content)
    else:
        return HttpResponseServerError()

def refresh_profiles(request, extra_content=dict()):
    return list_profiles(request, extra_content, refresh=True)

def view_session(request, session_id):
    if request.user.is_authenticated:
        (user,_,quser,qgroups) = _get_user(request)
        status, sessions = services.get_session_info(quser, qgroups, session_id=session_id)
        if status and len(sessions) > 0:
            for key in sessions[0]:
                session_id = key
            content = {
                "session_d": key,
                'session': sessions[0][key],
                'login': request.user.is_authenticated,
                'is_admin': user.is_staff
            }

            # logger.debug(content)
            return render(request, 'session_view.html', content)
        else:
            return HttpResponseNotFound()
    else:
        return HttpResponseRedirect('/')


def refresh_node(request):
    if not request.user.is_authenticated:
        return HttpResponseRedirect('/')

    (user,_,quser,qgroups) = _get_user(request)
    status, nodes = services.get_nodes(quser, qgroups, verbose=True, refresh=True)
    if status:
        content = {
            'nodes': nodes,
            'login': request.user.is_authenticated,
            'is_admin': user.is_staff
        }
        return render(request, 'node.html', content)
    else:
        return HttpResponseServerError()

def add_node(request):
    if not request.user.is_authenticated:
        return HttpResponseRedirect('/')

    (user,_,quser,qgroups) = _get_user(request)
    if user.is_staff:
        data = {"errors": list()}
        if request.method == 'POST':
            name = request.POST.get('name', None)
            if name is not None and len(name):
                data['name'] = name
            else:
                data['errors'].append("Invalid name")
            url = request.POST.get('url', None)
            if url is not None and len(name):
                data['url'] = url
            else:
                data['errors'].append("Invalid URL")
            ntype = request.POST.get('ntype', None)
            if ntype is not None:
                data['type'] = int(ntype)

            # XXX use django Forms...
            if not len(data['errors']):
                data['kwargs'] = {}
                status, res = services.add_node(data, quser, qgroups)
                if status:
                    return HttpResponseRedirect(reverse('janus:list_nodes'))
                else:
                    data['errors'].append(res)

        content = {
            'data': data,
            'ntypes': services.get_node_types(),
            'login': request.user.is_authenticated,
            'is_admin': user.is_staff
        }
        return render(request, 'add_node.html', content)
    else:
        return HttpResponseRedirect('/')


def remove_node(request, nname):
    if not request.user.is_authenticated:
        return HttpResponseRedirect('/')

    (user,_,quser,qgroups) = _get_user(request)
    status, _ = services.remove_node(nname, quser, qgroups)
    if status:
        return HttpResponseRedirect(reverse('janus:list_nodes'))
    else:
        return HttpResponseServerError()


def create_session(request):
    if not request.user.is_authenticated:
        return HttpResponseRedirect('/')

    (user,_,quser,qgroups) = _get_user(request)
    data = {"errors": list()}
    if request.method == 'POST':
        node = request.POST.getlist('node', None)
        if node is not None:
            data['instances'] = node

        image = request.POST.get('image', None)
        if image is not None:
            data['image'] = image

        tag = request.POST.get('image_tag', 'latest')
        if not tag:
            tag = 'latest'
        data['image'] = data['image'] + f":{tag}"

        profile = request.POST.get('profile', "default")
        if profile is not None:
            data['profile'] = profile

        data['arguments'] = request.POST.get('arguments', None)

        data['kwargs'] = {}
        ssh_user_name = request.POST.get('ssh_user_name', None)
        if ssh_user_name is not None:
            data['kwargs']['USER_NAME'] = ssh_user_name

        ssh_public_key = request.POST.get('ssh_public_key', None)
        if ssh_public_key is not None:
            data['kwargs']['PUBLIC_KEY'] = ssh_public_key

        data['remove_container'] = request.POST.get('remove_container', None)

        # XXX use django Forms...
        if not len(data['errors']):
            status, res = services.create_session(data, quser, qgroups)
            # look for errors for earch created service
            errs = dict()
            for sid,s in res.items():
                if 'services' in s:
                    for k,v in s['services'].items():
                        for n in v:
                            if len(n['errors']):
                                errs.update({k: n['errors']})
            if status and not errs:
                return HttpResponseRedirect(reverse('janus:list_sessions'))
            else:
                data["errors"].append(errs if errs else res)

    _, nodes = services.get_nodes(quser, qgroups, verbose=True)
    _, profiles = services.get_profiles(quser, qgroups)
    _, images = services.get_images(quser, qgroups)

    content = {
        'data': data,
        'nodes': nodes,
        'profiles': sorted(profiles),
        'images': images,
        'login': request.user.is_authenticated,
        'is_admin': user.is_staff
    }

    logger.debug(content)
    return render(request, 'create_session.html', content)


def update_profile(request, resource=Constants.HOST):
    def get_range(r, key):
        start = r.get(f"{key}_start")
        end = r.get(f"{key}_end")
        if not len(start) or not len(end):
            return None
        else:
            return [int(start), int(end)]

    def handle_host(request):
        pfields = dict()
        pfields['name'] = request.POST.get('name')
        s = dict()
        s['privileged'] = True if request.POST.get('privileged') else False
        s['systemd'] = True if request.POST.get('systemd') else False
        s['pull_image'] = True if request.POST.get('pull_image') else False
        s['cpu'] = False if not int(request.POST.get('cpu')) else int(request.POST.get('cpu'))
        s['memory'] = False if not int(request.POST.get('memory'))*1024*1024*1024 else int(request.POST.get('memory'))*1024*1024*1024
        s['mgmt_net'] = None if request.POST.get('mgmt_net') == Constants.NONE else request.POST.get('mgmt_net')
        s['data_net'] = None if request.POST.get('data_net') == Constants.NONE else request.POST.get('data_net')
        s['mgmt_net_ipv4'] = None if not len(request.POST.get('mgmt_net_ipv4')) else request.POST.get('mgmt_net_ipv4')
        s['mgmt_net_ipv6'] = None if not len(request.POST.get('mgmt_net_ipv6')) else request.POST.get('mgmt_net_ipv6')
        s['data_net_ipv4'] = None if not len(request.POST.get('data_net_ipv4')) else request.POST.get('data_net_ipv4')
        s['data_net_ipv6'] = None if not len(request.POST.get('data_net_ipv6')) else request.POST.get('data_net_ipv6')
        s['ctrl_port_range'] = get_range(request.POST, 'ctrl_port_range')
        s['serv_port_range'] = get_range(request.POST, 'serv_port_range')
        s['data_port_range'] = get_range(request.POST, 'data_port_range')
        s['affinity'] = None if not len(request.POST.get('affinity')) else request.POST.get('affinity')
        s['arguments'] = None if not len(request.POST.get('arguments')) else request.POST.get('arguments')
        s['qos'] = None if request.POST.get('qos') == Constants.NONE else request.POST.get('qos')
        s['volumes'] = request.POST.getlist('volumes')
        #s['environment'] = list() if not len(request.POST.get('environment')) else request.POST.get('environment')
        pfields['settings'] = s
        return pfields

    def handle_net(request):
        pfields = dict()
        pfields['name'] = request.POST.get('name')
        s = dict()
        s['driver'] = None if not len(request.POST.get('driver')) else request.POST.get('driver')
        s['mode'] = None if not len(request.POST.get('mode')) else request.POST.get('mode')
        s['enable_ipv6'] = True if request.POST.get('enable_ipv6') else False
        s['ipam'] = None
        s['options'] = None
        subnet = None if not len(request.POST.getlist('subnet')) else request.POST.getlist('subnet')
        gateway = None if not len(request.POST.getlist('gateway')) else request.POST.getlist('gateway')
        opt_name = None if not len(request.POST.getlist('opt_name')) else request.POST.getlist('opt_name')
        opt_value = None if not len(request.POST.getlist('opt_value')) else request.POST.getlist('opt_value')
        if subnet:
            config = list()
            ipam = dict()
            idx = 0
            while idx < (len(subnet)):
                addrs_dict = dict()
                addrs_dict.update({'subnet': subnet[idx]})
                addrs_dict.update({'gateway': gateway[idx]})
                config.append(addrs_dict)
                idx += 1
            ipam.update({'config': config})
            s['ipam'] = ipam

        if opt_name:
            options = dict()
            idx = 0
            while idx < (len(opt_name)):
                options.update({opt_name[idx]: opt_value[idx]})
                idx += 1
            s['options'] = options

        pfields['settings'] = s
        return pfields

    def handle_vol(request):
        pfields = dict()
        pfields['name'] = request.POST.get('name')
        s = dict()
        s['type'] = None if not len(request.POST.get('type')) else request.POST.get('type')
        s['driver'] = None if not len(request.POST.get('type')) else request.POST.get('driver')
        s['source'] = None if not len(request.POST.get('source')) else request.POST.get('source')
        s['target'] = None if not len(request.POST.get('target')) else request.POST.get('target')
        pfields['settings'] = s
        return pfields

    if not request.user.is_authenticated:
        return HttpResponseRedirect('/')

    (user,_,quser,qgroups) = _get_user(request)

    if request.method == 'POST':
        if resource == Constants.HOST:
            pfields = handle_host(request)
        elif resource == Constants.NET:
            pfields = handle_net(request)
        elif resource == Constants.VOL:
            pfields = handle_vol(request)

        data = {"errors": list()}
        content = {
            'data': data
        }
        status, res = services.update_profile(resource, pfields, quser, qgroups)
        if status:
            return HttpResponseRedirect(reverse('janus:list_profiles'))
        else:
            data["errors"].append(res)
        return list_profiles(request, content)


def create_profile(request, resource=Constants.HOST):
    if not request.user.is_authenticated:
        return HttpResponseRedirect('/')
    (user,_,quser,qgroups) = _get_user(request)
    if user.is_staff:
        data = {"errors": list()}
        name = request.POST.get('name', None)
        if resource == Constants.HOST:
            if request.method == 'POST':
                if not name:
                    data["errors"].append("Invalid name")

                data['privileged'] = request.POST.get('privileged', "default")
                data['systemd'] = request.POST.get('systemd', "default")
                data['pull_image'] = request.POST.get('pull_image', "default")
                for opt in ['privileged', 'systemd', 'pull_image']:
                    data[opt] = True if data[opt] == 'on' else False

                data['cpu'] = request.POST.get('cpu', 0)
                if not data['cpu']:
                    data["cpu"] = 0
                data["cpu"] = int(data["cpu"])

                data['memory'] = request.POST.get('memory', 0)
                if not data['memory']:
                    data['memory'] = 0
                data['memory'] = int(data['memory'])

                data['mgmt_net'] = request.POST.get('mgmt_net', "bridge")

                data['internal_port'] = request.POST.get('internal_port', None)
                if not data['internal_port']:
                    data['internal_port'] = None
                data['internal_port'] = int(data['internal_port']) if data['internal_port'] else None

                data['mgmt_net_ipv4'] = request.POST.get('mgmt_net_ipv4', None)
                data['mgmt_net_ipv6'] = request.POST.get('mgmt_net_ipv6', None)
                data['data_net_ipv4'] = request.POST.get('data_net_ipv4', None)
                data['data_net_ipv6'] = request.POST.get('data_net_ipv6', None)

                data['ctrl_port_range'] = request.POST.get('ctrl_port_range', None)
                data['data_port_range'] = request.POST.get('data_port_range', None)
                data['serv_port_range'] = request.POST.get('serv_port_range', None)


                data['affinity'] = request.POST.get('affinity', "network")
                if not data['affinity']:
                    data['affinity'] = 'network'


                data['arguments'] = request.POST.get('arguments', None)

                data['volumes'] = request.POST.getlist('volumes', None)

                data['qos'] = request.POST.get('qos', None)
                if not data['qos']:
                    data["qos"] = None

                data['environment'] = request.POST.getlist('environment', None)
                if not data['environment']:
                    data['environment'] = list()

                profile = {
                    'name': name,
                    'settings': data
                }

                # XXX use django Forms...
                if not len(data['errors']):
                    status, res = services.create_profile(resource, profile, quser, qgroups)
                    if status:
                        return HttpResponseRedirect(reverse('janus:list_profiles'))
                    else:
                        data["errors"].append(res)

            _, qos_choices = services.get_profiles(quser, qgroups, resource=Constants.QOS, verbose=True)
            _, vol_choices = services.get_profiles(quser, qgroups, resource=Constants.VOL, verbose=True)
            _, net_choices = services.get_profiles(quser, qgroups, resource=Constants.NET, verbose=True)
            kwargs = {Constants.QOS: [k.get('name') for k in qos_choices],
                      Constants.NET: [k.get('name') for k in net_choices],
                      Constants.VOL: [k.get('name') for k in vol_choices]}

            forms = ContainerProfileForm(pfields=None, **kwargs)
            content = {
                'data': data,
                'login': request.user.is_authenticated,
                'is_admin': user.is_staff,
                'forms': forms
            }
            logger.debug(content)
            return render(request, 'profile_create.html', content)

        elif resource == Constants.VOL:
            if request.method == 'POST':
                if not name:
                    data["errors"].append("Invalid name")
                data['type'] = request.POST.get('type', None)
                data['source'] = None if not len(request.POST.get('source')) else request.POST.get('source')
                data['target'] = None if not len(request.POST.get('target')) else request.POST.get('target')
                data['driver'] = None if not len(request.POST.get('driver')) else request.POST.get('driver')

                volume = {
                    'name': name,
                    'settings': data
                }

                if not len(data['errors']):
                    status, res = services.create_profile(resource, volume, quser, qgroups)
                    if status:
                        return HttpResponseRedirect(reverse('janus:list_profiles'))
                    else:
                        data["errors"].append(res)

            forms = VolumeProfileForm(vfields=None)
            content = {
                'data': data,
                'login': request.user.is_authenticated,
                'is_admin': user.is_staff,
                'forms': forms
            }
            logger.debug(content)
            return render(request, 'create_volume.html', content)



        elif resource == Constants.NET:
            if request.method == 'POST':
                if not name:
                    data["errors"].append("Invalid name")
                data['driver'] = request.POST.get('driver', None)
                data['mode'] = None if not len(request.POST.get('mode')) else request.POST.get('mode')
                data['enable_ipv6'] = True if request.POST.get('enable_ipv6') else False

                data['ipam'] = None
                subnet = request.POST.getlist('subnet', None)
                gateway = request.POST.getlist('gateway', None)
                config = list()
                if subnet[0]:
                    ipam = dict()
                    idx = 0
                    while idx < (len(subnet)):
                        addrs_dict = dict()
                        addrs_dict.update({'subnet': subnet[idx]})
                        addrs_dict.update({'gateway': gateway[idx]})
                        config.append(addrs_dict)
                        idx += 1
                    ipam.update({'config': config})
                    data['ipam'] = ipam

                data['options'] = None
                opts = request.POST.getlist('opt_name', None)
                opts_values = request.POST.getlist('opt_value', None)
                if len(opts) != 0:
                    options = dict()
                    idx = 0
                    while idx < (len(opts)):
                        options.update({opts[idx]: opts_values[idx]})
                        idx += 1
                    data['options'] = options

                network = {
                    'name': name,
                    'settings': data
                }

                if not len(data['errors']):
                    status, res = services.create_profile(resource, network, quser, qgroups)
                    if status:
                        return HttpResponseRedirect(reverse('janus:list_profiles'))
                    else:
                        data["errors"].append(res)

            forms = NetworkProfileForm(nfields=None)
            content = {
                'data': data,
                'login': request.user.is_authenticated,
                'is_admin': user.is_staff,
                'forms': forms
            }
            return render(request, 'create_network.html', content)

    else:
        return HttpResponseRedirect('/')


def start_session(request, session_id):
    if request.user.is_authenticated:
        data = {"errors": list()}
        (user,_,quser,qgroups) = _get_user(request)
        status, res = services.start_session(session_id, quser, qgroups)
        if status:
            _get_res_errors(data, res)
        else:
            data['errors'].append(res)
        return list_sessions(request, data)
    else:
        return HttpResponseRedirect('/')

def stop_session(request, session_id):
    if request.user.is_authenticated:
        data = {"errors": list()}
        (user,_,quser,qgroups) = _get_user(request)
        status, res = services.stop_session(session_id, quser, qgroups)
        if status:
            _get_res_errors(data, res)
        else:
            data['errors'].append(res)
        return list_sessions(request, data)
    else:
        return HttpResponseRedirect('/')

def delete_session(request, session_id):
    if request.user.is_authenticated:
        data = {"errors": list()}
        (user,_,quser,qgroups) = _get_user(request)
        status, res = services.delete_session(session_id, quser, qgroups)
        if status:
            _get_res_errors(data, res)
        else:
            data['errors'].append(res)
        return list_sessions(request, data)
    else:
        return HttpResponseRedirect('/')

def delete_profile(request, pname, resource=Constants.HOST):
    if request.user.is_authenticated:
        (user,_,quser,qgroups) = _get_user(request)
        status, _ = services.delete_profile(resource, pname, quser, qgroups)
        if status:
            return HttpResponseRedirect(reverse('janus:list_profiles'))
        else:
            return HttpResponseServerError()
    else:
        return HttpResponseRedirect('/')

# Non-template response views
def view_log(request, session_id, nname):
    ts = request.GET.get('timestamps')
    (status, log) = services.get_log(session_id, nname, ts)
    if status:
        return JsonResponse(log)
    else:
        return JsonResponse({"error": "Could not find logs"})

