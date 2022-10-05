import logging
from . import services
from django.shortcuts import render, HttpResponseRedirect
from django.http import HttpResponseServerError, HttpResponseNotFound
from django.urls import reverse


logger = logging.getLogger(__name__)

def list_sessions_by_user(request):
    if "name" in request.session:
        name = request.user
        login = True
        sessions = services.get_sessions_by_user(name)

        content = {
            "name": name,
            "login": login,
            "sessions": sessions
        }

        return render(request, 'home.html', content)
    else:
        return HttpResponseRedirect('/login/')


def list_sessions(request):
    status, sessions = services.get_session_info()
    login = request.user.is_authenticated
    content = {
        'login': login
    }

    if status:
        if login:
            content['sessions'] = sessions
        else:
            content['sessions'] = [session for session in sessions if session['profile'] == 'public']

        logger.info(content)
        return render(request, 'home.html', content)
    else:
        return HttpResponseServerError()


def list_nodes(request):
    status, nodes = services.get_nodes(verbose=True)
    if status:
        content = {
            'nodes': nodes,
            'login': request.user.is_authenticated
        }

        return render(request, 'node.html', content)
    else:
        return HttpResponseServerError()


def list_profiles(request):
    status, profiles = services.get_profiles(verbose=True)
    # logger.info(profiles)
    if status:
        content = {
            "profiles": profiles,
            'login': request.user.is_authenticated
        }

        return render(request, 'profile.html', content)
    else:
        return HttpResponseServerError()


def view_session(request, session_id):
    status, sessions = services.get_session_info(session_id=session_id)
    if status and len(sessions) > 0:
        for key in sessions[0]:
            session_id = key
        content = {
            "session_d": key,
            'session': sessions[0][key],
            'login': request.user.is_authenticated
        }

        # logger.debug(content)
        return render(request, 'session_view.html', content)
    else:
        return HttpResponseNotFound()

def add_node(request):
    login = request.user.is_authenticated
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
            status, res = services.add_node(data)
            if status:
                return HttpResponseRedirect(reverse('janus:list_nodes'))
            else:
                data['errors'].append(res)

    content = {
        'data': data,
        'ntypes': services.get_node_types(),
        'login': request.user.is_authenticated
    }
    return render(request, 'add_node.html', content)


def remove_node(request, nname):
    if request.user.is_authenticated:
        status, res = services.remove_node(nname)
        if status:
            return HttpResponseRedirect(reverse('janus:list_nodes'))
        else:
            return HttpResponseServerError()
    else:
        return HttpResponseRedirect('/')


def create_session(request):
    login = request.user.is_authenticated
    # if not login:
    #     return HttpResponseRedirect('/')

    data = {"errors": list()}
    if request.method == 'POST':
        node = request.POST.get('node', None)
        if node is not None:
            data['instances'] = [node]

        image = request.POST.get('image', None)
        if image is not None:
            data['image'] = image

        profile = request.POST.get('profile', "default")
        if profile is not None:
            data['profile'] = profile

        data['kwargs'] = {}
        ssh_user_name = request.POST.get('ssh_user_name', None)
        if ssh_user_name is not None:
            data['kwargs']['USER_NAME'] = ssh_user_name

        ssh_public_key = request.POST.get('ssh_public_key', None)
        if ssh_public_key is not None:
            data['kwargs']['PUBLIC_KEY'] = ssh_public_key

        # XXX use django Forms...
        if not len(data['errors']):
            status, res = services.create_session(data)
            if status:
                return HttpResponseRedirect(reverse('janus:list_sessions'))
            else:
                data["errors"].append(res)

    _, nodes = services.get_nodes()
    if login:
        _, profiles = services.get_profiles()
        _, images = services.get_images(nodes[0])
    else:
        profiles = ["public"]
        images = ["dtnaas/tools:latest"]

    content = {
        'data': data,
        'nodes': nodes,
        'profiles': profiles,
        'images': images,
        'login': request.user.is_authenticated
    }

    logger.debug(content)
    return render(request, 'create_session.html', content)


def create_profile(request):
    if not request.user.is_authenticated:
        return HttpResponseRedirect('/')

    data = {"errors": list()}
    if request.method == 'POST':
        name = request.POST.get('name', None)
        if not name:
            data["errors"].append("Invalid name")
        data['cpu'] = request.POST.get('cpu', 0)
        if not data['cpu']:
            data["cpu"] = 0
        data["cpu"] = int(data["cpu"])

        data['mem'] = request.POST.get('memory', 0)
        if not data['mem']:
            data['mem'] = 0
        data['mem'] = int(data['mem'])

        data['affinity'] = request.POST.get('affinity', "network")
        data['mgmt_net'] = request.POST.get('mgmt_net', "bridge")

        data['internal_port'] = request.POST.get('internal_port', None)
        if not data['internal_port']:
            data['internal_port'] = None

        data['internal_port'] = int(data['internal_port']) if data['internal_port'] else None
        data['qos'] = request.POST.get('qos', None)
        if not data['qos']:
            data["qos"] = None

        profile = {
            'name': name,
            'settings': data
        }

        # XXX use django Forms...
        if not len(data['errors']):        
            status, res = services.create_profile(profile)
            if status:
                return HttpResponseRedirect(reverse('janus:list_profiles'))
            else:
                data["errors"].append(res)

    _, qos = services.get_qos()
    content = {
        'data': data,
        'qos': qos,
        'login': request.user.is_authenticated
    }

    logger.debug(content)
    return render(request, 'create_profile.html', content)



def start_session(request, session_id):
    if request.user.is_authenticated:
        status, _ = services.start_session(session_id)
        if status:
            return HttpResponseRedirect(reverse('janus:list_sessions'))
        else:
            return HttpResponseServerError()
    else:
        return HttpResponseRedirect('/')


def stop_session(request, session_id):
    if request.user.is_authenticated:
        status, _ = services.stop_session(session_id)
        if status:
            return HttpResponseRedirect(reverse('janus:list_sessions'))
        else:
            return HttpResponseServerError()
    else:
        return HttpResponseRedirect('/')


def delete_session(request, session_id):
    if request.user.is_authenticated:
        status, _ = services.delete_session(session_id)
        if status:
            return HttpResponseRedirect(reverse('janus:list_sessions'))
        else:
            return HttpResponseServerError()
    else:
        return HttpResponseRedirect('/')


def delete_profile(request, pname):
    if request.user.is_authenticated:
        status, _ = services.delete_profile(pname)
        if status:
            return HttpResponseRedirect(reverse('janus:list_profiles'))
        else:
            return HttpResponseServerError()
    else:
        return HttpResponseRedirect('/')

