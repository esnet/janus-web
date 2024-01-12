from .constants import Constants
from django.urls import reverse
from django import forms
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Hidden, Div, Layout, Submit

class VolumeCreateForm(forms.Form):
    def __init__(self, *args, **kwargs):
        vfields = kwargs.pop('vfields')
        super(VolumeCreateForm, self).__init__(*args, **kwargs)
        anytext = {'name': 'Name:',
                   'type': 'Type:',
                   'driver': 'Driver:',
                   'source': 'Source:',
                   'target': 'Target:'}

        for keys in list(anytext.keys()):
            if keys not in list(vfields["settings"].keys()):
                vfields["settings"].update({keys: None})

        for key, value in vfields["settings"].items():
             if key in anytext.keys():
                 self.fields[key] = forms.CharField(widget=forms.TextInput(attrs={}),
                                                initial=value, required=False, label=anytext[key],
                                                max_length=255)


class NetworkCreateForm(forms.Form):
    def __init__(self, *args, **kwargs):
        nfields = kwargs.pop('nfields')
        super(NetworkCreateForm, self).__init__(*args, **kwargs)
        bools = {'enable_ipv6': 'Enable IPv6'}
        anytext = {'name': 'Name:',
                   'driver': 'Driver:',
                   'mode': 'Mode:',
                   'subnet': 'Subnet:',
                   'gateway': 'Gateway:',
                   'options': 'Option:',
                   'values': 'Value:'}

        for keys in list(anytext.keys()):
            if keys not in list(nfields["settings"].keys()):
                nfields["settings"].update({keys: None})

        for keys in list(bools.keys()):
            if keys not in list(nfields["settings"].keys()):
                nfields["settings"].update({keys: "default"})

        for key, value in nfields["settings"].items():
            if key in bools:
                self.fields[key] = forms.BooleanField(widget=forms.CheckboxInput(attrs={'id': f"{nfields['name']}-{key}"}),
                                                      required=False, label=bools[key],
                                                      initial=False if value=="default" else value)
            elif key in anytext.keys():
                self.fields[key] = forms.CharField(widget=forms.TextInput(attrs={}),
                                                   initial=value, required=False, label=anytext[key],
                                                   max_length=255)

class ContainerCreateForm(forms.Form):
    def __init__(self, *args, **kwargs):
        pfields = kwargs.pop('pfields')
        qos_choices = kwargs.pop('qos')
        mgmt_net_choices = kwargs.pop('network').copy()
        volumes_choices = kwargs.pop('volume').copy()
        super(ContainerCreateForm, self).__init__(*args, **kwargs)

        bools = {'privileged': 'Privileged Container:',
                 'systemd': 'Systemd Container:',
                 'pull_image': 'Pull Image on Create:'}
        selects = {'cpu': 'Cores:',
                   'memory': 'Memory:'}
        selects_none = {'qos': 'Quality of Service:',
                        'mgmt_net': 'Management Network:',
                        'data_net': 'Dataplane Network:'}
        multichoice = {'volumes': 'Volumes:'}
        # textareas = {'environment': 'Environment Variables'}
        anytext = {'name': 'Name:',
                   'arguments': 'Arguments (Container Cmd):',
                   'mgmt_net_ipv4': 'Management IPv4 Address:',
                   'mgmt_net_ipv6': 'Management IPv6 Address:',
                   'data_net_ipv4': 'Data IPv4 Address:',
                   'data_net_ipv6': 'Data IPv6 Address:',
                   'affinity': 'Affinity:',
                   'environment': 'Environment Variables:'}
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

        field_types = [bools, selects, selects_none, multichoice, anytext, anytext, ranges]
        for fields in field_types:
            for keys in list(fields.keys()):
                if keys not in list(pfields["settings"].keys()):
                    pfields["settings"].update({keys: None})

        for key, value in pfields["settings"].items():
            if key in bools:
                self.fields[key] = forms.BooleanField(widget=forms.CheckboxInput(attrs={'id': f"{pfields['name']}-{key}"}),
                                                      required=False, label=bools[key],
                                                      initial=False if value=="default" else value)
            elif key in selects_none.keys():
                self.fields[key] = forms.ChoiceField(choices=locals().get(f"{key}_choices", tuple()),
                                                     initial=Constants.NONE if not value else value,
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
            # elif key in textareas.keys():
            #     self.fields[key] = forms.CharField(widget=forms.Textarea(attrs={'rows': 4, 'readonly':'readonly'}),
            #                                        initial=value, required=False, label=textareas[key])
            elif key in ranges.keys():
                self.fields[f"{key}_start"] = forms.CharField(widget=forms.TextInput(attrs={'type': 'number'}),
                                                              initial=value[0] if value else "",
                                                              required=False, label = f"{ranges[key]} Start:")
                self.fields[f"{key}_end"] = forms.CharField(widget=forms.TextInput(attrs={'type': 'number'}),
                                                            initial=value[1] if value else "",
                                                            required=False, label = f"{ranges[key]} End:")
            elif key in anytext.keys():
                self.fields[key] = forms.CharField(widget=forms.TextInput(attrs={}),
                                                   initial=value, required=False, label=anytext[key],
                                                   max_length=255)
            elif key in multichoice.keys():
                self.fields[key] = forms.MultipleChoiceField(choices=locals().get(f"{key}_choices", tuple()),
                                                             initial=value, required=False, label=multichoice[key])
            else:
                self.fields[key] = forms.CharField(widget=forms.TextInput(attrs={'pattern': '[a-zA-Z0-9]+'}),
                                                   initial=value, required=False)

        self.helper = FormHelper()
        self.helper.layout = Layout(
            Div(
                Div('name', css_class='col-sm-12 d-flex justify-content-center'),
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


class VolumeProfileForm(forms.Form):
    def __init__(self, *args, **kwargs):
        vfields = kwargs.pop('vfields')
        super(VolumeProfileForm, self).__init__(*args, **kwargs)
        anytext = {'type': 'Type',
                   'driver': 'Driver',
                   'source': 'Source',
                   'target': 'Target'}

        # for keys in list(anytext.keys()):
        #     if keys not in list(vfields["settings"].keys()):
        #         vfields["settings"].update({keys: Constants.NONE})

        for key, value in vfields["settings"].items():
             if key in anytext.keys():
                 self.fields[key] = forms.CharField(widget=forms.TextInput(attrs={}),
                                                initial=value, required=False, label=anytext[key],
                                                max_length=255)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Hidden('name', value=vfields["name"]),
            Div(
                Div('type', css_class='col-sm-6'),
                Div('driver', css_class='col-sm-6'),
                Div('source', css_class='col-sm-6'),
                Div('target', css_class='col-sm-6'),
                css_class='row'
            )
        )
        self.helper.add_input(Submit('submit', 'Save', css_class='btn btn-primary'))
        self.helper.form_method = 'POST'
        self.helper.form_action = reverse('janus:update_profile', args=[Constants.VOL])


class NetworkProfileForm(forms.Form):
    def __init__(self, *args, **kwargs):
        nfields = kwargs.pop('nfields')
        super(NetworkProfileForm, self).__init__(*args, **kwargs)

        bools = {'enable_ipv6': 'Enable IPv6'}
        anytext = {'driver': 'Driver',
                   'mode': 'Mode',
                   'ipam': 'IPAM',
                   'options': 'Options'}

        # for keys in list(anytext.keys()):
        #     if keys not in list(nfields["settings"].keys()):
        #         nfields["settings"].update({keys: Constants.NONE})
        #
        # for keys in list(bools.keys()):
        #     if keys not in list(nfields["settings"].keys()):
        #         nfields["settings"].update({keys: None})

        for key, value in nfields["settings"].items():
            if key in bools:
                self.fields[key] = forms.BooleanField(
                    widget=forms.CheckboxInput(attrs={'id': f"{nfields['name']}-{key}"}),
                    required=False, label=bools[key],
                    initial=False if value == "default" else value)

            elif key in anytext.keys():
                if key=='ipam':
                    placeholder = "e.g. [{'subnet':'192.168.1.2', 'gateway':'192.168.1.1'}]"
                    if value is not None:
                        self.fields[key] = forms.CharField(widget=forms.TextInput(attrs={'placeholder': placeholder}),
                                                   initial=value["config"], required=False, label=anytext[key],
                                                   max_length=255)
                    elif value is None:
                        self.fields[key] = forms.CharField(widget=forms.TextInput(attrs={'placeholder': placeholder}),
                                                   required=False, label=anytext[key],
                                                   max_length=255)

                elif key=='options':
                    placeholder = "e.g. {'parent': 'enp0s3', 'mtu': 9100}"
                    if value is not None:
                        self.fields[key] = forms.CharField(widget=forms.TextInput(attrs={'placeholder': placeholder}),
                                                   initial=value, required=False, label=anytext[key],
                                                   max_length=255)
                    elif value is None:
                        self.fields[key] = forms.CharField(widget=forms.TextInput(attrs={'placeholder': placeholder}),
                                                   required=False, label=anytext[key],
                                                   max_length=255)

                else:
                    self.fields[key] = forms.CharField(widget=forms.TextInput(attrs={}),
                                                   initial=value, required=False, label=anytext[key],
                                                   max_length=255)

        self.helper = FormHelper()
        self.helper.layout = Layout(
            Hidden('name', value=nfields["name"]),
            Div(
                Div('enable_ipv6', css_class='col-sm-8'),
                Div('driver', css_class='col-sm-6'),
                Div('mode', css_class='col-sm-6'),
                Div('ipam', css_class='col-sm-6'),
                Div('options', css_class='col-sm-6'),
                css_class='row'
            )
        )
        self.helper.add_input(Submit('submit', 'Save', css_class='btn btn-primary'))
        self.helper.form_method = 'POST'
        self.helper.form_action = reverse('janus:update_profile', args=[Constants.NET])




class ContainerProfileForm(forms.Form):
    def __init__(self, *args, **kwargs):
        pfields = kwargs.pop('pfields')
        qos_choices = kwargs.pop('qos').copy()
        mgmt_net_choices = kwargs.pop('network').copy()
        volumes_choices = kwargs.pop('volume').copy()
        super(ContainerProfileForm, self).__init__(*args, **kwargs)

        bools = {'privileged': 'Privileged Container',
                 'systemd': 'Systemd Container',
                 'pull_image': 'Pull Image on Create'}
        selects = {'cpu': 'Cores',
                   'memory': 'Memory'}
        selects_none = {'qos': 'Quality of Service',
                        'mgmt_net': 'Management Network',
                        'data_net': 'Dataplane Network'}
        multichoice = {'volumes': 'Volumes'}
        textareas = {'environment': 'Environment Variables'}
        anytext = {'arguments': 'Arguments (Container Cmd)',
                   'mgmt_net_ipv4': 'Management IPv4 Address',
                   'mgmt_net_ipv6': 'Management IPv6 Address',
                   'data_net_ipv4': 'Data IPv4 Address',
                   'data_net_ipv6': 'Data IPv6 Address'}
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

        for key, value in pfields["settings"].items():
            if key in bools:
                self.fields[key] = forms.BooleanField(widget=forms.CheckboxInput(attrs={'id': f"{pfields['name']}-{key}"}),
                                                      required=False, label=bools[key],
                                                      initial=False if value=="default" else value)
            elif key in selects_none.keys():
                self.fields[key] = forms.ChoiceField(choices=locals().get(f"{key}_choices", tuple()),
                                                     initial=Constants.NONE if not value else value,
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
            elif key in multichoice.keys():
                self.fields[key] = forms.MultipleChoiceField(choices=locals().get(f"{key}_choices", tuple()),
                                                             initial=value, required=False, label=multichoice[key])
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
                Div('memory', css_class='col-sm-6'),
                Div('mgmt_net', css_class='col-sm-6'),
                Div('mgmt_net_ipv4', css_class='col-sm-3'),
                Div('mgmt_net_ipv6', css_class='col-sm-3'),
                Div('data_net', css_class='col-sm-6'),
                Div('data_net_ipv4', css_class='col-sm-3'),
                Div('data_net_ipv6', css_class='col-sm-3'),
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
        self.helper.form_action = reverse('janus:update_profile', args=[Constants.HOST])

