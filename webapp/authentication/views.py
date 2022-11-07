import logging
from django.contrib.auth import authenticate, login, logout
from django.shortcuts import HttpResponseRedirect, render
from django.contrib.auth.models import User, Group
from janus.services import get_nodes, get_profiles, get_images
from .services import set_access

logger = logging.getLogger(__name__)

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


def image_access_control(request):
    if not request.user.is_authenticated:
        return HttpResponseRedirect('/')

    user = User.objects.get(username=request.user)
    if user.is_staff:
        quser = None
        qgroups = None

        status, images = get_images(quser, qgroups)
        # print(status, images)
        users = User.objects.filter(is_active=True).values_list('username', flat=True)
        groups = Group.objects.all().values_list('name', flat=True)
        data = {"errors": list()}

        if request.method == 'POST':
            image = request.POST.get('image', None)
            if image is None:
                data['errors'].append('Image not found!')

            data['image'] = image

            selected_users = request.POST.getlist('user', [])
            data['users'] = selected_users

            selected_groups = request.POST.getlist('group', [])
            data['groups'] = selected_groups

            # print(data)
            if not len(data['errors']):
                status, res = set_access("images", data)
                if status:
                    return HttpResponseRedirect("/")
                else:
                    data["errors"].append(res)

        if status:
            content = {
                "data": data,
                'images': images,
                'login': request.user.is_authenticated,
                'is_admin': user.is_staff,
                'users': users,
                'groups': groups
            }
            return render(request, 'auth_image.html', content)

    return HttpResponseRedirect('/')


def node_access_control(request):
    if not request.user.is_authenticated:
        return HttpResponseRedirect('/')

    user = User.objects.get(username=request.user)
    if user.is_staff:
        quser = None
        qgroups = None

        status, nodes = get_nodes(quser, qgroups, verbose=True)
        users = User.objects.filter(is_active=True).values_list('username', flat=True)
        groups = Group.objects.all().values_list('name', flat=True)

        # print(f'users: {users}\ngroups: {groups}')
        data = {"errors": list()}

        if request.method == 'POST':
            node = request.POST.get('node', None)
            if node is None:
                data['errors'].append('Node not found!')

            data['node'] = node
            selected_users = request.POST.getlist('user', [])
            data['users'] = selected_users

            selected_groups = request.POST.getlist('group', [])
            data['groups'] = selected_groups

            # print(data)
            if not len(data['errors']):
                status, res = set_access("nodes", data)
                if status:
                    return HttpResponseRedirect("/")
                else:
                    data["errors"].append(res)

        if status:
            content = {
                "data": data,
                'nodes': nodes,
                'login': request.user.is_authenticated,
                'is_admin': user.is_staff,
                'users': users,
                'groups': groups
            }
            return render(request, 'auth_node.html', content)

    return HttpResponseRedirect('/')


def profile_access_control(request):
    if not request.user.is_authenticated:
        return HttpResponseRedirect('/')

    user = User.objects.get(username=request.user)
    if user.is_staff:
        quser = None
        qgroups = None

        status, profiles = get_profiles(quser, qgroups, verbose=True)
        users = User.objects.filter(is_active=True).values_list('username', flat=True)
        groups = Group.objects.all().values_list('name', flat=True)
        data = {"errors": list()}

        if request.method == 'POST':
            profile = request.POST.get('profile', None)
            if profile is None:
                data['errors'].append('Profile not found!')

            data['profile'] = profile

            selected_users = request.POST.getlist('user', [])
            data['users'] = selected_users

            selected_groups = request.POST.getlist('group', [])
            data['groups'] = selected_groups

            # print(data)
            if not len(data['errors']):
                status, res = set_access("profiles", data)
                if status:
                    return HttpResponseRedirect("/")
                else:
                    data["errors"].append(res)

        if status:
            content = {
                "data": data,
                'profiles': profiles,
                'login': request.user.is_authenticated,
                'is_admin': user.is_staff,
                'users': users,
                'groups': groups
            }
            return render(request, 'auth_profile.html', content)

    return HttpResponseRedirect('/')