from django.contrib.auth import authenticate, login, logout
from django.shortcuts import HttpResponseRedirect

def login_view(request):
    if request.method == 'POST':
        username = request.POST.get('username', None)
        password = request.POST.get('password', None)
        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
        else:
            logout(request)

    return HttpResponseRedirect('/')


def logout_view(request):
    logout(request)
    return HttpResponseRedirect('/')
