from .constants import Constants
from django.urls import reverse
from django import forms
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Hidden, Div, Layout, Submit, Button, Field, HTML

class VolumeProfileForm(forms.Form):
    def __init__(self, *args, **kwargs):
        vfields = kwargs.pop('vfields')
        super(VolumeProfileForm, self).__init__(*args, **kwargs)
        anytext = {'type': 'Type',
                   'driver': 'Driver',
                   'source': 'Source',
                   'target': 'Target'}
        if not vfields:
            anytext.update({'name': 'Name'})

        for key, label in anytext.items():
            value = None
            if vfields and key in vfields.get('settings'):
                value = vfields['settings'].get(key)
            self.fields[key] = forms.CharField(widget=forms.TextInput(attrs={}),
                                               initial=value, required=False, label=label,
                                               max_length=255)
        self.helper = FormHelper()
        name_layout = Hidden('name', value=vfields["name"]) if vfields else Div('name', css_class='col-sm-6')
        self.helper.layout = Layout(
            name_layout,
            Div(
                Div('type', css_class='col-sm-6'),
                Div('driver', css_class='col-sm-6'),
                css_class='form-row'
            ),
            Div(
                Div('source', css_class='col-sm-6'),
                Div('target', css_class='col-sm-6'),
                css_class='form-row'
            )
        )
        self.helper.add_input(Submit('submit', 'Save', css_class='btn btn-primary'))
        self.helper.form_method = 'POST'
        if vfields:
            self.helper.form_action = reverse('janus:update_profile', args=[Constants.VOL])
        else:
            self.helper.add_input(Button('cancel', 'Cancel', css_class='btn btn-primary',
                                         onclick="window.location.href = '{}';".format(reverse('janus:list_profiles'))))
            self.helper.form_action = reverse('janus:create_profile', args=[Constants.VOL])


class NetworkProfileForm(forms.Form):
    def __init__(self, *args, **kwargs):
        nfields = kwargs.pop('nfields')
        super(NetworkProfileForm, self).__init__(*args, **kwargs)

        bools = {'enable_ipv6': 'Enable IPv6'}
        anytext = {'driver': 'Driver',
                   'mode': 'Mode',
                   'ipam': 'IPAM',
                   'options': 'Options'}

        if not nfields:
            anytext.update({'name': 'Name'})

        name = nfields.get('name') if nfields else "new"
        for key, label in {**bools, **anytext}.items():
            value = None
            if nfields and key in nfields.get('settings'):
                value = nfields['settings'].get(key)
            if key in bools:
                self.fields[key] = forms.BooleanField(
                    widget=forms.CheckboxInput(attrs={'id': f"{name}-{key}"}),
                    required=False, label=bools[key],
                    initial=False if value == "default" else value)

            elif key in ['name', 'driver', 'mode']:
                self.fields[key] = forms.CharField(widget=forms.TextInput(attrs={}),
                                                   initial=value, required=False, label=anytext[key],
                                                   max_length=255)

        self.helper = FormHelper()
        name_layout = Hidden('name', value=name) if nfields else Div('name', css_class='col-sm-6')
        self.helper.layout = Layout(
            name_layout,
            Div(
                Div('enable_ipv6', css_class='col-sm-3'),
                css_class='checkbox-inline'
            ),
            Div(
                Div('driver', css_class='col-sm-6'),
                Div('mode', css_class='col-sm-6'),
                css_class='form-row'
            )
        )
        self.helper.add_input(Submit('submit', 'Save', css_class='btn btn-primary'))
        self.helper.form_method = 'POST'
        if nfields:
            self.helper.form_action = reverse('janus:update_profile', args=[Constants.NET])
        else:
            self.helper.add_input(Button('cancel', 'Cancel', css_class='btn btn-primary',
                                         onclick="window.location.href = '{}';".format(reverse('janus:list_profiles'))))
            self.helper.form_action = reverse('janus:create_profile', args=[Constants.NET])

        self.helper.layout.append(HTML("<p>IPAM</p>"))
        self.helper.layout.append(HTML("""
        <div class='form-row align-items-center d-flex justify-content-center'>
          <div class='col-sm-4'><i>Subnet</i></div>
          <div class='col-sm-4'><i>Gateway</i></div>
        </div>
        """))
        self.fields['subnet'] = forms.CharField(widget=forms.TextInput(attrs={}),
                                                label=False,
                                                required=False)
        self.fields['gateway'] = forms.CharField(widget=forms.TextInput(attrs={}),
                                                 label=False,
                                                 required=False)
        self.helper.layout.append(
            Div(
                Div(
                    Field('subnet', wrapper_class='col-sm-4', v_model='row.subnet'),
                    Field('gateway', wrapper_class='col-sm-4', v_model='row.gateway'),
                    HTML('<a v-on:click="rows.push({})" class="btn btn-sm btn-success"><span class="fa-solid fa-plus"></span></a>'),
                    HTML('<a v-on:click="rows.splice(index, 1)" class="btn btn-sm btn-danger"><span class="fa-solid fa-xmark"></span></a>'),
                    css_class='form-row align-items-center d-flex justify-content-center',
                    v_for=f'row in rows'
                ),
                id=f"ipam-app-{name}", css_class="ipam-app", key='blah'
            )
        )

        self.helper.layout.append(HTML("<p>Options</p>"))
        self.helper.layout.append(HTML("""
        <div class='form-row align-items-center d-flex justify-content-center'>
          <div class='col-sm-4'><i>Name</i></div>
          <div class='col-sm-4'><i>Value</i></div>
        </div>
        """))
        self.fields['opt_name'] = forms.CharField(widget=forms.TextInput(attrs={}),
                                                  label=False,
                                                  required=False)
        self.fields['opt_value'] = forms.CharField(widget=forms.TextInput(attrs={}),
                                                   label=False,
                                                   required=False)
        self.helper.layout.append(
            Div(
                Div(
                    Field('opt_name', wrapper_class='col-sm-4', v_model='row.name'),
                    Field('opt_value', wrapper_class='col-sm-4', v_model='row.value'),
                    HTML('<a v-on:click="rows.push({})" class="btn btn-sm btn-success"><span class="fa-solid fa-plus"></span></a>'),
                    HTML('<a v-on:click="rows.splice(index, 1)" class="btn btn-sm btn-danger"><span class="fa-solid fa-xmark"></span></a>'),
                    css_class='form-row align-items-center d-flex justify-content-center',
                    v_for='row in rows'
                ),
                id=f"options-app-{name}", css_class="options-app"
            )
        )


class ContainerProfileForm(forms.Form):
    def __init__(self, *args, **kwargs):
        pfields = kwargs.pop('pfields')
        qos_choices = kwargs.pop('qos')
        mgmt_net_choices = kwargs.pop('network').copy()
        volumes_choices = kwargs.pop('volume').copy()
        super(ContainerProfileForm, self).__init__(*args, **kwargs)

        bools = {'privileged': 'Privileged Container:',
                 'systemd': 'Systemd Container:',
                 'pull_image': 'Pull Image on Create:'}
        selects = {'cpu': 'Cores:',
                   'memory': 'Memory:'}
        selects_none = {'qos': 'Quality of Service:',
                        'mgmt_net': 'Management Network:',
                        'data_net': 'Dataplane Network:'}
        multichoice = {'volumes': 'Volumes:'}
        textareas = {'environment': 'Environment Variables'}
        anytext = {
                   'arguments': 'Arguments (Container Cmd):',
                   'mgmt_net_ipv4': 'Management IPv4 Address:',
                   'mgmt_net_ipv6': 'Management IPv6 Address:',
                   'data_net_ipv4': 'Data IPv4 Address:',
                   'data_net_ipv6': 'Data IPv6 Address:',
                   'affinity': 'Affinity:',
                   'environment': 'Environment Variables:'}

        if not pfields:
            anytext.update({'name': 'Name'})

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
        memory_choices = (
            ('0', 'default'),
            ('1', '1 GB'),
            ('2', '2 GB'),
            ('4', '4 GB'),
            ('8', '8 GB'),
            ('16', '16 GB'),
            ('32', '32 GB')
        )

        qos_choices.append(Constants.NONE)
        qos_choices = sorted(tuple(zip(qos_choices, qos_choices)))
        mgmt_net_choices.append(Constants.NONE)
        mgmt_net_choices = sorted(tuple(zip(mgmt_net_choices, mgmt_net_choices)))
        data_net_choices = mgmt_net_choices
        volumes_choices = sorted(tuple(zip(volumes_choices, volumes_choices)))

        name = pfields.get('name') if pfields else "new"
        for key, label in {**bools, **selects, **selects_none, **multichoice, **textareas, **anytext, **ranges}.items():
            value = None
            if pfields and key in pfields.get('settings'):
                value = pfields['settings'].get(key)
            if key in bools:
                self.fields[key] = forms.BooleanField(
                    widget=forms.CheckboxInput(attrs={'id': f"{name}-{key}"}),
                    required=False, label=bools[key],
                    initial=False if value == "default" else value)

            elif key in anytext:
                self.fields[key] = forms.CharField(widget=forms.TextInput(attrs={}),
                                                   initial=value, required=False, label=anytext[key],
                                                   max_length=255)

            elif key in selects_none:
                self.fields[key] = forms.ChoiceField(choices=locals().get(f"{key}_choices", tuple()),
                                                     initial=Constants.NONE if not value else value,
                                                     required=False, label=selects_none[key])

            elif key in selects:
                try:
                    parts = value.split(" ")
                    if len(parts):
                        value = parts[0]
                except:
                    pass
                self.fields[key] = forms.ChoiceField(choices=locals().get(f"{key}_choices", tuple()),
                                                     initial=0 if value=="default" else value,
                                                     required=False, label=selects[key])

            elif key in textareas:
                self.fields[key] = forms.CharField(widget=forms.Textarea(attrs={'rows': 4, 'readonly':'readonly'}),
                                                   initial=value, required=False, label=textareas[key])

            elif key in ranges:
                self.fields[f"{key}_start"] = forms.CharField(widget=forms.TextInput(attrs={'type': 'number'}),
                                                              initial=value[0] if value else "",
                                                              required=False, label = f"{ranges[key]} Start:")
                self.fields[f"{key}_end"] = forms.CharField(widget=forms.TextInput(attrs={'type': 'number'}),
                                                            initial=value[1] if value else "",
                                                            required=False, label = f"{ranges[key]} End:")

            elif key in multichoice.keys():
                self.fields[key] = forms.MultipleChoiceField(choices=locals().get(f"{key}_choices", tuple()),
                                                             initial=value, required=False, label=multichoice[key])

            else:
                self.fields[key] = forms.CharField(widget=forms.TextInput(attrs={'pattern': '[a-zA-Z0-9]+'}),
                                                   initial=value, required=False)

        self.helper = FormHelper()
        name_layout = Div('name', css_class='col-sm-6') if not pfields else Hidden('name', value=pfields["name"])
        self.helper.layout = Layout(
            name_layout,
            Div(
                Div('privileged', css_class='col-4'),
                Div('systemd', css_class='col-4'),
                Div('pull_image', css_class='col-4'),
                Div('cpu', css_class='col-sm-6'),
                Div('memory', css_class='col-sm-6'),
                Div('mgmt_net', css_class='col-sm-4'),
                Div('mgmt_net_ipv4', css_class='col-sm-4'),
                Div('mgmt_net_ipv6', css_class='col-sm-4'),
                Div('data_net', css_class='col-sm-4'),
                Div('data_net_ipv4', css_class='col-sm-4'),
                Div('data_net_ipv6', css_class='col-sm-4'),
                Div('ctrl_port_range_start', css_class='col-sm-6'),
                Div('ctrl_port_range_end', css_class='col-sm-6'),
                Div('data_port_range_start', css_class='col-sm-6'),
                Div('data_port_range_end', css_class='col-sm-6'),
                Div('serv_port_range_start', css_class='col-sm-6'),
                Div('serv_port_range_end', css_class='col-sm-6'),
                Div('affinity', css_class='col-sm-6'),
                # Div('features', css_class='col-sm-6'),
                Div('arguments', css_class='col-sm-6'),
                Div('volumes', css_class='col-sm-6'),
                Div('qos', css_class='col-sm-6'),
                Div('environment', css_class='col-sm-12 justify-content-center'),
                css_class='row'
            )
        )
        self.helper.add_input(Submit('submit', 'Save', css_class='btn btn-primary'))
        self.helper.form_method = 'POST'
        if pfields:
            self.helper.form_action = reverse('janus:update_profile', args=[Constants.HOST])
        else:
            self.helper.add_input(Button('cancel', 'Cancel', css_class='btn btn-primary',
                                         onclick="window.location.href = '{}';".format(reverse('janus:list_profiles'))))
            self.helper.form_action = reverse('janus:create_profile', args=[Constants.HOST])

