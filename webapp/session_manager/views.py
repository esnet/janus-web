import logging
from urllib import response

from requests import session
from . import services
from django.shortcuts import render, HttpResponseRedirect
from django.http import HttpResponseServerError

logger = logging.getLogger(__name__)


def list_sessions_by_user(request):
    login = False
    if "name" in request.session:
        name = request.session["name"]
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
            'sessions': sessions
        }

        return render(request, 'home.html', content)
    else:
        return HttpResponseServerError()


def view_session(request, session_id):
    logger.debug(services.get_session_info())
    logger.debug('view_session called with session_id: %s', session_id)
    content = {
        'session_id': session_id
    }

    return render(request, 'session_view.html', content)


def create_session(request):
    logger.debug('create_session called')
    return HttpResponseRedirect('/')


def start_session(request, session_id):
    status, _ = services.start_session(session_id)
    if status:
        return HttpResponseRedirect('/session/')
    else:
        return HttpResponseServerError()


def stop_session(request, session_id):
    status, _ = services.stop_session(session_id)
    if status:
        return HttpResponseRedirect('/session/')
    else:
        return HttpResponseServerError()


def delete_session(request, session_id):
    status, _ = services.delete_session(session_id)
    if status:
        return HttpResponseRedirect('/session/')
    else:
        return HttpResponseServerError()

