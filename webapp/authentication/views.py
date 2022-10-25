from asyncio.log import logger
from django.contrib.auth import authenticate, login, logout
from django.shortcuts import HttpResponseRedirect, render
from django.contrib.auth.models import User


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


def signup_view(request):
    errors = []
    if request.method == 'POST':
        username = request.POST.get('username', None)
        password = request.POST.get('password', None)
        email = request.POST.get('email', None)

        if username is not None:
            if User.objects.filter(username=username).exists():
                errors.append('Username already exists!')
        else:
            errors.append('Must provide username!')

        if password is not None:
            if len(password) < 8:
                errors.append('Password must be at least 8 characters!')
        else:
            errors.append('Must provide password!')

        if email is not None:
            if User.objects.filter(email=email).exists():
                errors.append('Email already exists!')
        else:
            errors.append('Must provide email!')

        if not errors:
            try:
                user = User.objects.create_user(username=username, password=password, email=email)
                if user is not None:
                    login(request, user)
                    return HttpResponseRedirect('/')
            except Exception as e:
                errors.append(str(e))

    content = {
        'errors': errors
    }

    return render(request, 'signup.html', content)
