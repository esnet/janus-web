import logging
import json
from django.contrib.auth import authenticate, login, logout
from django.shortcuts import HttpResponseRedirect, render
from django.urls import reverse
from django.contrib.auth.models import User, Group
from django.http import JsonResponse
from janus.services import get_nodes, get_profiles, get_images, get_session_info
from janus.constants import Constants
from .services import set_access, set_access_bulk

logger = logging.getLogger(__name__)


def login_view(request):
    if request.method == "POST":
        username = request.POST.get("username", None)
        password = request.POST.get("password", None)
        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
        else:
            logout(request)

    return HttpResponseRedirect("/")


def logout_view(request):
    logout(request)
    return HttpResponseRedirect("/")


def signup_view(request):
    errors = []
    if request.method == "POST":
        username = request.POST.get("username", None)
        password = request.POST.get("password", None)
        email = request.POST.get("email", None)

        if username is not None:
            if User.objects.filter(username=username).exists():
                errors.append("Username already exists!")
        else:
            errors.append("Must provide username!")

        if password is not None:
            if len(password) < 8:
                errors.append("Password must be at least 8 characters!")
        else:
            errors.append("Must provide password!")

        if email is not None:
            if User.objects.filter(email=email).exists():
                errors.append("Email already exists!")
        else:
            errors.append("Must provide email!")

        if not errors:
            try:
                user = User.objects.create_user(
                    username=username, password=password, email=email
                )
                if user is not None:
                    login(request, user)
                    return HttpResponseRedirect("/")
            except Exception as e:
                errors.append(str(e))

    content = {"errors": errors}

    return render(request, "signup.html", content)


def image_access_control(request):
    if not request.user.is_authenticated:
        return HttpResponseRedirect("/")

    user = User.objects.get(username=request.user)
    if user.is_staff:
        quser = None
        qgroups = None

        status, images = get_images(quser, qgroups)
        users = User.objects.filter(is_active=True).values_list("username", flat=True)
        groups = Group.objects.all().values_list("name", flat=True)
        data = {"errors": list()}

        if request.method == "POST":
            remove = True if "remove" in request.POST else False
            image = request.POST.get("image", None)
            if image is None:
                data["errors"].append("Image not found!")

            data["image"] = image

            selected_users = request.POST.getlist("user", [])
            data["users"] = selected_users

            selected_groups = request.POST.getlist("group", [])
            data["groups"] = selected_groups

            if not len(data["errors"]):
                status, res = set_access("images", data, remove)
                if status:
                    return HttpResponseRedirect(reverse("auth_images"))
                else:
                    data["errors"].append(res)

        if status:
            content = {
                "data": data,
                "images": images,
                "login": request.user.is_authenticated,
                "is_admin": user.is_staff,
                "users": users,
                "groups": groups,
            }
            return render(request, "auth_image.html", content)

    return HttpResponseRedirect("/")


def node_access_control(request):
    if not request.user.is_authenticated:
        return HttpResponseRedirect("/")

    user = User.objects.get(username=request.user)
    if user.is_staff:
        quser = None
        qgroups = None

        status, nodes = get_nodes(quser, qgroups, verbose=True)
        users = User.objects.filter(is_active=True).values_list("username", flat=True)
        groups = Group.objects.all().values_list("name", flat=True)

        data = {"errors": list()}

        if request.method == "POST":
            remove = True if "remove" in request.POST else False
            node = request.POST.get("node", None)
            if node is None:
                data["errors"].append("Node not found!")

            data["node"] = node
            selected_users = request.POST.getlist("user", [])
            data["users"] = selected_users

            selected_groups = request.POST.getlist("group", [])
            data["groups"] = selected_groups

            if not len(data["errors"]):
                status, res = set_access("nodes", data, remove)
                if status:
                    return HttpResponseRedirect(reverse("auth_nodes"))
                else:
                    data["errors"].append(res)

        if status:
            content = {
                "data": data,
                "nodes": nodes,
                "login": request.user.is_authenticated,
                "is_admin": user.is_staff,
                "users": users,
                "groups": groups,
            }
            return render(request, "auth_node.html", content)

    return HttpResponseRedirect("/")


def profile_access_control(request):
    if not request.user.is_authenticated:
        return HttpResponseRedirect("/")

    user = User.objects.get(username=request.user)
    if user.is_staff:
        quser = None
        qgroups = None

        status, profiles = get_profiles(quser, qgroups, verbose=True)
        users = User.objects.filter(is_active=True).values_list("username", flat=True)
        groups = Group.objects.all().values_list("name", flat=True)
        data = {"errors": list()}

        if request.method == "POST":
            remove = True if "remove" in request.POST else False
            profile = request.POST.get("profile", None)
            if profile is None:
                data["errors"].append("Profile not found!")

            data["profile"] = profile

            selected_users = request.POST.getlist("user", [])
            data["users"] = selected_users

            selected_groups = request.POST.getlist("group", [])
            data["groups"] = selected_groups

            if not len(data["errors"]):
                status, res = set_access("profiles", data, remove)
                if status:
                    return HttpResponseRedirect(reverse("auth_profiles"))
                else:
                    data["errors"].append(res)

        if status:
            content = {
                "data": data,
                "profiles": profiles,
                "login": request.user.is_authenticated,
                "is_admin": user.is_staff,
                "users": users,
                "groups": groups,
            }
            return render(request, "auth_profile.html", content)

    return HttpResponseRedirect("/")


def sessions_access_control(request):
    if not request.user.is_authenticated:
        return HttpResponseRedirect("/")

    user = User.objects.get(username=request.user)
    if user.is_staff:
        quser = None
        qgroups = None

        status, sessions = get_session_info(quser, qgroups)
        users = User.objects.filter(is_active=True).values_list("username", flat=True)
        groups = Group.objects.all().values_list("name", flat=True)
        data = {"errors": list()}

        if request.method == "POST":
            remove = True if "remove" in request.POST else False
            session_id = request.POST.get("id", None)
            if session_id is None:
                data["errors"].append("Active Session not found!")

            data["session_id"] = session_id

            selected_users = request.POST.getlist("user", [])
            data["users"] = selected_users

            selected_groups = request.POST.getlist("group", [])
            data["groups"] = selected_groups

            if not len(data["errors"]):
                status, res = set_access("active", data, remove)
                if status:
                    return HttpResponseRedirect(reverse("auth_sessions"))
                else:
                    data["errors"].append(res)

        if status:
            content = {
                "data": data,
                "sessions": sessions,
                "login": request.user.is_authenticated,
                "is_admin": user.is_staff,
                "users": users,
                "groups": groups,
            }

            return render(request, "auth_session.html", content)

    return HttpResponseRedirect("/")

# JSON API for Access Control
def get_access_info_api(request):
    if not request.user.is_authenticated or not request.user.is_staff:
        return JsonResponse({"error": "Unauthorized"}, status=401)

    users = list(User.objects.filter(is_active=True).values_list("username", flat=True))
    groups = list(Group.objects.all().values_list("name", flat=True))

    quser, qgroups = None, None
    _, nodes = get_nodes(quser, qgroups, verbose=True)
    _, profiles = get_profiles(quser, qgroups, verbose=True)
    _, images = get_images(quser, qgroups)
    _, sessions = get_session_info(quser, qgroups)

    return JsonResponse(
        {
            "users": users,
            "groups": groups,
            "nodes": nodes,
            "profiles": profiles,
            "images": images,
            "sessions": sessions,
        }
    )


def update_access_api(request):
    if not request.user.is_authenticated or not request.user.is_staff:
        return JsonResponse({"error": "Unauthorized"}, status=401)

    if request.method == "POST":
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON"}, status=400)

        resource = data.get("resource")
        remove = data.get("remove", False)
        # set_access expects specific keys based on resource
        if resource == "nodes":
            data["node"] = data.get("identifier")
        elif resource == "images":
            data["image"] = data.get("identifier")
        elif resource == "profiles":
            data["profile"] = data.get("identifier")
        elif resource == "active":
            data["session_id"] = data.get("identifier")

        status, res = set_access(resource, data, remove)
        return JsonResponse(
            {"success": status, "result": res}, status=200 if status else 400
        )

    return JsonResponse({"error": "Method not allowed"}, status=405)

def access_control_dashboard(request, tab="nodes"):
    if not request.user.is_authenticated or not request.user.is_staff:
        return HttpResponseRedirect("/")
    
    content = {
        "active_tab": tab,
        "login": request.user.is_authenticated,
        "is_admin": request.user.is_staff,
        "user": request.user.username,
    }
    return render(request, "access_control.html", content)

def update_access_bulk_api(request):
    if not request.user.is_authenticated or not request.user.is_staff:
        return JsonResponse({"error": "Unauthorized"}, status=401)

    if request.method == "POST":
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON"}, status=400)

        resource = data.get("resource")
        remove = data.get("remove", False)
        
        status, res = set_access_bulk(resource, data, remove)
        return JsonResponse(
            {"success": status, "result": res}, status=200 if status else 400
        )

    return JsonResponse({"error": "Method not allowed"}, status=405)
