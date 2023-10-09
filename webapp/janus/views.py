import logging
from . import services
from django.contrib.auth.models import User
from django.shortcuts import render, HttpResponseRedirect
from django.http import HttpResponseServerError, HttpResponseNotFound, JsonResponse
from django.urls import reverse
from django import forms
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Hidden, Div, Layout, Submit

logger = logging.getLogger(__name__)

class ProfileForm(forms.Form):
    def __init__(self, *args, **kwargs):
        pfields = kwargs.pop('pfields')
        qos_choices = kwargs.pop('qos').copy()
        super(ProfileForm, self).__init__(*args, **kwargs)

        bools = {'privileged': 'Privileged Container',
                 'systemd': 'Systemd Container',
                 'pull_image': 'Pull Image on Create'}
        selects = {'cpu': 'Cores',
                   'mem': 'Memory'}
        selects_none = {'qos': 'Quality of Service'}
        textareas = {'environment': 'Environment Variables',
                    'volumes': 'Volumes'}
        anytext = {'arguments': "Arguments (Container Cmd)"}
        ranges = {'ctrl_port_range': 'Control Port Range',
                  'serv_port_range': 'Service Port Range',
                  'data_port_range': 'Data Port Range'}

        cpu_choices = (
            ('0', 'default'),
            ('1', '1'),
            ('2', '2'),
            ('4', '4'),
            ('8', '8'),
            ('16', '16'),
            ('32', '32'),
            ('64', '64'),
            ('128', '128')
        )
        mem_choices = (
            ('0', 'default'),
            ('1', '1 GB'),
            ('2', '2 GB'),
            ('4', '4 GB'),
            ('8', '8 GB'),
            ('16', '16 GB'),
            ('32', '32 GB')
        )

        qos_choices.append('None')
        qos_choices = tuple(zip(qos_choices, qos_choices))

        for key, value in pfields["settings"].items():
            if key in bools:
                self.fields[key] = forms.BooleanField(widget=forms.CheckboxInput(attrs={'id': f"{pfields['name']}-{key}"}),
                                                      required=False, label=bools[key],
                                                      initial=False if value=="default" else value)
            elif key in selects_none.keys():
                self.fields[key] = forms.ChoiceField(choices=locals().get(f"{key}_choices", tuple()),
                                                     initial='None' if not value else value,
                                                     required=False, label=selects_none[key])
            elif key in selects.keys():
                try:
                    parts = value.split(" ")
                    if len(parts):
                        value = parts[0]
                except:
                    pass
                self.fields[key] = forms.ChoiceField(choices=locals().get(f"{key}_choices", tuple()),
                                                     initial=0 if value=="default" else value,
                                                     required=False, label=selects[key])
            elif key in textareas.keys():
                self.fields[key] = forms.CharField(widget=forms.Textarea(attrs={'rows': 4, 'readonly':'readonly'}),
                                                   initial=value, required=False, label=textareas[key])
            elif key in ranges.keys():
                self.fields[f"{key}_start"] = forms.CharField(widget=forms.TextInput(attrs={'type': 'number'}),
                                                              initial=value[0] if value else "",
                                                              required=False, label = f"{ranges[key]} Start")
                self.fields[f"{key}_end"] = forms.CharField(widget=forms.TextInput(attrs={'type': 'number'}),
                                                            initial=value[1] if value else "",
                                                            required=False, label = f"{ranges[key]} End")
            elif key in anytext.keys():
                self.fields[key] = forms.CharField(widget=forms.TextInput(attrs={}),
                                                   initial=value, required=False, label=anytext[key],
                                                   max_length=255)
            else:
                self.fields[key] = forms.CharField(widget=forms.TextInput(attrs={'pattern': '[a-zA-Z0-9]+'}),
                                                   initial=value, required=False)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Hidden('name', value=pfields["name"]),
            Div(
                Div('privileged', css_class='col-4 border d-flex justify-content-center'),
                Div('systemd', css_class='col-4 border d-flex justify-content-center'),
                Div('pull_image', css_class='col-4 border d-flex justify-content-center'),
                Div('cpu', css_class='col-sm-6'),
                Div('mem', css_class='col-sm-6'),
                Div('mgmt_net', css_class='col-sm-6'),
                Div('data_net', css_class='col-sm-6'),
                Div('ctrl_port_range_start', css_class='col-sm-3'),
                Div('ctrl_port_range_end', css_class='col-sm-3'),
                Div('data_port_range_start', css_class='col-sm-3'),
                Div('data_port_range_end', css_class='col-sm-3'),
                Div('serv_port_range_start', css_class='col-sm-3'),
                Div('serv_port_range_end', css_class='col-sm-3'),
                Div('affinity', css_class='col-sm-6'),
                #Div('features', css_class='col-sm-6'),
                Div('arguments', css_class='col-sm-6'),
                Div('volumes', css_class='col-sm-6'),
                Div('qos', css_class='col-sm-6'),
                Div('environment', css_class='col-sm-6'),
                css_class='row'
            )
        )
        self.helper.add_input(Submit('submit', 'Save', css_class='btn btn-primary'))
        self.helper.form_method = 'POST'
        self.helper.form_action = reverse('janus:update_profile')


def _get_user(request):
    user = User.objects.get(username=request.user)
    groups = list(user.groups.all())
    quser = user.username
    qgroups = [g.name for g in groups]
    if user.is_staff:
        quser = None
        qgroups = None
    return (user, groups, quser, qgroups)


def list_sessions(request):
    if not request.user.is_authenticated:
        return HttpResponseRedirect('/')

    (user,_,quser,qgroups) = _get_user(request)
    status, sessions = services.get_session_info(quser, qgroups)
    login = request.user.is_authenticated
    content = {
        'user': user.username,
        'login': login,
        'is_admin': user.is_staff,
    }

    if status:
        content['sessions'] = sessions
        # logger.info(content)
        return render(request, 'home.html', content)
    else:
        return HttpResponseServerError()


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

def list_profiles(request, extra_content=dict()):
    if not request.user.is_authenticated:
        return HttpResponseRedirect('/')

    (user,_,quser,qgroups) = _get_user(request)
    status, profiles = services.get_profiles(quser, qgroups, verbose=True)
    _, qos_choices = services.get_qos()
    kwargs = {"qos": qos_choices}
    forms = dict()
    for p in profiles:
        forms.update({p['name']: ProfileForm(pfields=p, **kwargs)})
    if status:
        content = {
            "profiles": profiles,
            'login': request.user.is_authenticated,
            'is_admin': user.is_staff,
            'forms': forms
        }
        content.update(extra_content)
        return render(request, 'profile.html', content)
    else:
        return HttpResponseServerError()

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


def refresh_profile(request, extra_content=dict()):
    if not request.user.is_authenticated:
        return HttpResponseRedirect('/')

    (user,_,quser,qgroups) = _get_user(request)
    status, profiles = services.get_profiles(quser, qgroups, verbose=True, refresh=True)
    _, qos_choices = services.get_qos()
    kwargs = {"qos": qos_choices}
    forms = dict()
    for p in profiles:
        forms.update({p['name']: ProfileForm(pfields=p, **kwargs)})
    if status:
        content = {
            "profiles": profiles,
            'login': request.user.is_authenticated,
            'is_admin': user.is_staff,
            'forms': forms
        }
        content.update(extra_content)
        return render(request, 'profile.html', content)
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


def update_profile(request):
    def get_range(r, key):
        start = r.get(f"{key}_start")
        end = r.get(f"{key}_end")
        if not len(start) or not len(end):
            return None
        else:
            return [int(start), int(end)]

    if not request.user.is_authenticated:
        return HttpResponseRedirect('/')

    (user,_,quser,qgroups) = _get_user(request)

    if request.method == 'POST':
        data = {"errors": list()}
        pfields = dict()
        pfields['name'] = request.POST.get('name')
        s = dict()
        s['privileged'] = True if request.POST.get('privileged') else False
        s['systemd'] = True if request.POST.get('systemd') else False
        s['pull_image'] = True if request.POST.get('pull_image') else False
        s['cpu'] = False if not int(request.POST.get('cpu')) else int(request.POST.get('cpu'))
        s['mem'] = False if not int(request.POST.get('mem'))*1024*1024*1024 else int(request.POST.get('mem'))*1024*1024*1024
        s['mgmt_net'] = None if not len(request.POST.get('mgmt_net')) else request.POST.get('mgmt_net')
        s['data_net'] = None if not len(request.POST.get('data_net')) else request.POST.get('data_net')
        s['ctrl_port_range'] = get_range(request.POST, 'ctrl_port_range')
        s['serv_port_range'] = get_range(request.POST, 'serv_port_range')
        s['data_port_range'] = get_range(request.POST, 'data_port_range')
        s['affinity'] = None if not len(request.POST.get('affinity')) else request.POST.get('affinity')
        s['arguments'] = None if not len(request.POST.get('arguments')) else request.POST.get('arguments')
        s['qos'] = None if request.POST.get('qos') == 'None' else request.POST.get('qos')
        #s['environment'] = list() if not len(request.POST.get('environment')) else request.POST.get('environment')
        pfields['settings'] = s

        content = {
            'data': data
        }
        status, res = services.update_profile(pfields, quser, qgroups)
        if status:
            return HttpResponseRedirect(reverse('janus:list_profiles'))
        else:
            data["errors"].append(res)
        return list_profiles(request, content) 


def create_profile(request):
    if not request.user.is_authenticated:
        return HttpResponseRedirect('/')

    (user,_,quser,qgroups) = _get_user(request)
    if user.is_staff:
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

            data['arguments'] = request.POST.get('arguments', None)

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
                status, res = services.create_profile(profile, quser, qgroups)
                if status:
                    return HttpResponseRedirect(reverse('janus:list_profiles'))
                else:
                    data["errors"].append(res)

        _, qos = services.get_qos()
        content = {
            'data': data,
            'qos': qos,
            'login': request.user.is_authenticated,
            'is_admin': user.is_staff
        }

        logger.debug(content)
        return render(request, 'create_profile.html', content)

    else:
        return HttpResponseRedirect('/')


def start_session(request, session_id):
    if request.user.is_authenticated:
        (user,_,quser,qgroups) = _get_user(request)
        status, _ = services.start_session(session_id, quser, qgroups)
        if status:
            return HttpResponseRedirect(reverse('janus:list_sessions'))
        else:
            return HttpResponseServerError()
    else:
        return HttpResponseRedirect('/')


def stop_session(request, session_id):
    if request.user.is_authenticated:
        (user,_,quser,qgroups) = _get_user(request)
        status, _ = services.stop_session(session_id, quser, qgroups)
        if status:
            return HttpResponseRedirect(reverse('janus:list_sessions'))
        else:
            return HttpResponseServerError()
    else:
        return HttpResponseRedirect('/')


def delete_session(request, session_id):
    if request.user.is_authenticated:
        (user,_,quser,qgroups) = _get_user(request)
        status, _ = services.delete_session(session_id, quser, qgroups)
        if status:
            return HttpResponseRedirect(reverse('janus:list_sessions'))
        else:
            return HttpResponseServerError()
    else:
        return HttpResponseRedirect('/')


def delete_profile(request, pname):
    if request.user.is_authenticated:
        (user,_,quser,qgroups) = _get_user(request)
        status, _ = services.delete_profile(pname, quser, qgroups)
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

