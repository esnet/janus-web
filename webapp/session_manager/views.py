import logging
from . import services
from django.shortcuts import render, HttpResponseRedirect
from django.http import HttpResponseServerError, HttpResponseNotFound

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
    if status:
        content = {
            'sessions': sessions,
            'login': request.user.is_authenticated
        }

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


def create_session(request):
    if not request.user.is_authenticated:
        return HttpResponseRedirect('/')

    if request.method == 'POST':
        data = {}
        node = request.POST.get('node', None)
        if node is not None:
            data['instances'] = [node]
        else:
            return HttpResponseRedirect('/session/create/')

        image = request.POST.get('image', None)
        if image is not None:
            data['image'] = image
        else:
            return HttpResponseRedirect('/session/create/')

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

        status, _ = services.create_session(data)
        if status:
            return HttpResponseRedirect('/session/')
        else:
            return HttpResponseRedirect('/session/create/')

    _, nodes = services.get_nodes()
    _, profiles = services.get_profiles()
    _, images = services.get_images(nodes[0])
    content = {
        'nodes': nodes,
        'profiles': profiles,
        'images': images,
        'login': request.user.is_authenticated
    }

    logger.debug(content)
    return render(request, 'create_session.html', content)


def start_session(request, session_id):
    if request.user.is_authenticated:
        status, _ = services.start_session(session_id)
        if status:
            return HttpResponseRedirect('/session/')
        else:
            return HttpResponseServerError()
    else:
        return HttpResponseRedirect('/')


def stop_session(request, session_id):
    if request.user.is_authenticated:
        status, _ = services.stop_session(session_id)
        if status:
            return HttpResponseRedirect('/session/')
        else:
            return HttpResponseServerError()
    else:
        return HttpResponseRedirect('/')


def delete_session(request, session_id):
    if request.user.is_authenticated:
        status, _ = services.delete_session(session_id)
        if status:
            return HttpResponseRedirect('/session/')
        else:
            return HttpResponseServerError()
    else:
        return HttpResponseRedirect('/')


def delete_profile(request, pname):
    if request.user.is_authenticated:
        status, _ = services.delete_profile(pname)
        if status:
            return HttpResponseRedirect('/session/profiles/')
        else:
            return HttpResponseServerError()
    else:
        return HttpResponseRedirect('/')

