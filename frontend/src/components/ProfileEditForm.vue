<template>
  <form @submit.prevent="save">
    <div class="row">
      <!-- Common Name Field -->
      <div class="col-md-6 mb-4">
        <label class="small font-weight-bold text-uppercase text-muted mb-1">Profile Name</label>
        <input v-model="form.name" type="text" class="form-control" :disabled="!isNew" required placeholder="e.g. high-performance">
      </div>
    </div>

    <hr class="mb-4">

    <!-- Host Profile Fields -->
    <div v-if="resource === 'host'">
      <div class="row mb-3">
        <div class="col-md-4">
          <div class="custom-control custom-checkbox mt-4">
            <input type="checkbox" class="custom-control-input" v-model="form.settings.privileged" id="check-priv">
            <label class="custom-control-label font-weight-bold small text-uppercase" for="check-priv">Privileged</label>
          </div>
        </div>
        <div class="col-md-4">
          <div class="custom-control custom-checkbox mt-4">
            <input type="checkbox" class="custom-control-input" v-model="form.settings.systemd" id="check-sysd">
            <label class="custom-control-label font-weight-bold small text-uppercase" for="check-sysd">Systemd</label>
          </div>
        </div>
        <div class="col-md-4">
          <div class="custom-control custom-checkbox mt-4">
            <input type="checkbox" class="custom-control-input" v-model="form.settings.pull_image" id="check-pull">
            <label class="custom-control-label font-weight-bold small text-uppercase" for="check-pull">Always Pull</label>
          </div>
        </div>
      </div>

      <div class="row mb-3">
        <div class="col-md-6">
          <label class="small font-weight-bold text-uppercase text-muted mb-1">CPU Cores</label>
          <select v-model="form.settings.cpu" class="custom-select custom-select-sm shadow-sm">
            <option value="0">Default</option>
            <option v-for="n in [1,2,4,8,16,32,64]" :key="n" :value="n">{{ n }}</option>
          </select>
        </div>
        <div class="col-md-6">
          <label class="small font-weight-bold text-uppercase text-muted mb-1">Memory Limit</label>
          <select v-model="form.settings.memory" class="custom-select custom-select-sm shadow-sm">
            <option value="0">Default</option>
            <option v-for="n in [1,2,4,8,16,32,64,128]" :key="n" :value="n * 1024 * 1024 * 1024">{{ n }} GB</option>
          </select>
        </div>
      </div>

      <div class="row mb-3 p-3 bg-light rounded mx-0 border">
        <div class="col-md-4">
          <label class="small font-weight-bold text-uppercase text-muted mb-1">Management Network</label>
          <select v-model="form.settings.mgmt_net" class="custom-select custom-select-sm shadow-sm mb-2">
            <option value="---">None</option>
            <option v-for="n in store.choices.networks" :key="n" :value="n">{{ n }}</option>
          </select>
        </div>
        <div class="col-md-4">
          <label class="small font-weight-bold text-uppercase text-muted mb-1">MGMT IPv4</label>
          <input v-model="form.settings.mgmt_net_ipv4" type="text" class="form-control form-control-sm shadow-sm" placeholder="Optional IP">
        </div>
        <div class="col-md-4">
          <label class="small font-weight-bold text-uppercase text-muted mb-1">MGMT IPv6</label>
          <input v-model="form.settings.mgmt_net_ipv6" type="text" class="form-control form-control-sm shadow-sm" placeholder="Optional IP">
        </div>
      </div>

      <div class="row mb-3 p-3 bg-light rounded mx-0 border mt-3">
        <div class="col-md-4">
          <label class="small font-weight-bold text-uppercase text-muted mb-1">Data Network</label>
          <select v-model="form.settings.data_net" class="custom-select custom-select-sm shadow-sm mb-2">
            <option value="---">None</option>
            <option v-for="n in store.choices.networks" :key="n" :value="n">{{ n }}</option>
          </select>
        </div>
        <div class="col-md-4">
          <label class="small font-weight-bold text-uppercase text-muted mb-1">Data IPv4</label>
          <input v-model="form.settings.data_net_ipv4" type="text" class="form-control form-control-sm shadow-sm" placeholder="Optional IP">
        </div>
        <div class="col-md-4">
          <label class="small font-weight-bold text-uppercase text-muted mb-1">Data IPv6</label>
          <input v-model="form.settings.data_net_ipv6" type="text" class="form-control form-control-sm shadow-sm" placeholder="Optional IP">
        </div>
      </div>

      <div class="row mb-3 mt-3">
        <div class="col-md-6">
          <label class="small font-weight-bold text-uppercase text-muted mb-1">QoS Profile</label>
          <select v-model="form.settings.qos" class="custom-select custom-select-sm shadow-sm">
            <option value="---">None</option>
            <option v-for="q in store.choices.qos" :key="q" :value="q">{{ q }}</option>
          </select>
        </div>
        <div class="col-md-6">
            <label class="small font-weight-bold text-uppercase text-muted mb-1">Volumes</label>
            <select v-model="form.settings.volumes" multiple class="form-control form-control-sm shadow-sm" style="height: 100px">
                <option v-for="v in store.choices.volumes" :key="v" :value="v">{{ v }}</option>
            </select>
            <small class="text-muted">Hold Ctrl/Cmd to select multiple</small>
        </div>
      </div>

      <div class="row mb-3">
          <div class="col-12">
            <label class="small font-weight-bold text-uppercase text-muted mb-1">Environment Variables</label>
            <textarea v-model="environmentText" class="form-control form-control-sm shadow-sm" rows="4" placeholder="KEY=VALUE (one per line)"></textarea>
          </div>
      </div>
    </div>

    <!-- Network Profile Fields -->
    <div v-else-if="resource === 'network'">
      <div class="row mb-3">
        <div class="col-md-4">
          <label class="small font-weight-bold text-uppercase text-muted mb-1">Driver</label>
          <input v-model="form.settings.driver" type="text" class="form-control form-control-sm" placeholder="e.g. bridge, macvlan">
        </div>
        <div class="col-md-4">
          <label class="small font-weight-bold text-uppercase text-muted mb-1">Mode</label>
          <input v-model="form.settings.mode" type="text" class="form-control form-control-sm" placeholder="e.g. bridge, vepa">
        </div>
        <div class="col-md-4">
          <div class="custom-control custom-checkbox mt-4">
            <input type="checkbox" class="custom-control-input" v-model="form.settings.enable_ipv6" id="check-ipv6">
            <label class="custom-control-label font-weight-bold small text-uppercase" for="check-ipv6">Enable IPv6</label>
          </div>
        </div>
      </div>
      
      <div class="row mb-3">
          <div class="col-12">
              <label class="small font-weight-bold text-uppercase text-muted mb-2">IPAM Configuration</label>
              <div v-for="(ipam, index) in ipamConfigs" :key="index" class="input-group input-group-sm mb-2 shadow-sm">
                  <div class="input-group-prepend"><span class="input-group-text bg-light">Subnet</span></div>
                  <input v-model="ipam.subnet" type="text" class="form-control" placeholder="10.0.0.0/24">
                  <div class="input-group-prepend ml-2"><span class="input-group-text bg-light">Gateway</span></div>
                  <input v-model="ipam.gateway" type="text" class="form-control" placeholder="10.0.0.1">
                  <div class="input-group-append ml-2">
                      <button class="btn btn-danger" type="button" @click="removeIpam(index)"><i class="fas fa-trash-alt"></i></button>
                  </div>
              </div>
              <button class="btn btn-outline-success btn-sm mt-2" type="button" @click="addIpam">
                  <i class="fas fa-plus-circle mr-1"></i> Add Subnet Configuration
              </button>
          </div>
      </div>
    </div>

    <!-- Volume Profile Fields -->
    <div v-else-if="resource === 'volume'">
      <div class="row mb-3">
        <div class="col-md-6">
          <label class="small font-weight-bold text-uppercase text-muted mb-1">Type</label>
          <input v-model="form.settings.type" type="text" class="form-control form-control-sm" placeholder="e.g. bind, volume">
        </div>
        <div class="col-md-6">
          <label class="small font-weight-bold text-uppercase text-muted mb-1">Driver</label>
          <input v-model="form.settings.driver" type="text" class="form-control form-control-sm" placeholder="e.g. local, ceph">
        </div>
      </div>
      <div class="row mb-3">
        <div class="col-md-6">
          <label class="small font-weight-bold text-uppercase text-muted mb-1">Source (Host Path)</label>
          <input v-model="form.settings.source" type="text" class="form-control form-control-sm" placeholder="/data/share">
        </div>
        <div class="col-md-6">
          <label class="small font-weight-bold text-uppercase text-muted mb-1">Target (Container Path)</label>
          <input v-model="form.settings.target" type="text" class="form-control form-control-sm" placeholder="/mnt/data">
        </div>
      </div>
    </div>

    <!-- QoS Profile Fields -->
    <div v-else-if="resource === 'qos'">
       <div class="row mb-3">
           <div class="col-md-4 mb-4" v-for="field in qosFields" :key="field">
               <label class="small font-weight-bold text-uppercase text-muted mb-1">{{ field }}</label>
               <input v-model="form.settings[field]" type="text" class="form-control form-control-sm" :placeholder="'e.g. ' + field">
           </div>
       </div>
    </div>

    <div class="mt-5 pt-4 border-top d-flex justify-content-between align-items-center">
      <button type="button" class="btn btn-outline-secondary px-4" @click="$emit('cancel')">
          <i class="fas fa-arrow-left mr-2"></i> Back to Dashboard
      </button>
      <button type="submit" class="btn btn-primary px-5 shadow-sm" :disabled="saving">
        <i class="fas mr-2" :class="saving ? 'fa-spinner fa-spin' : 'fa-save'"></i>
        {{ saving ? 'Processing...' : (isNew ? 'Create Profile' : 'Update Profile') }}
      </button>
    </div>
  </form>
</template>

<script setup>
import { ref, reactive } from 'vue';
import { useProfileStore } from '../stores/profileStore';

const props = defineProps(['resource', 'profile', 'isNew']);
const emit = defineEmits(['saved', 'cancel']);
const store = useProfileStore();

const saving = ref(false);

// Normalize settings: convert "default" strings to null/empty
const initialSettings = JSON.parse(JSON.stringify(props.profile.settings || {}));
Object.keys(initialSettings).forEach(key => {
    if (initialSettings[key] === 'default') {
        initialSettings[key] = null;
    }
});

const form = reactive({
    name: props.profile.name || '',
    settings: initialSettings
});

// Helper for Environment Variables
const environmentText = ref('');
if (form.settings.environment) {
    environmentText.value = Array.isArray(form.settings.environment) 
        ? form.settings.environment.join('\n') 
        : form.settings.environment === 'default' ? '' : form.settings.environment;
}

// Helper for IPAM
const ipamConfigs = ref([]);
if (form.settings.ipam && form.settings.ipam.config) {
    ipamConfigs.value = form.settings.ipam.config.map(c => ({ 
        subnet: c.subnet || c.Subnet || '', 
        gateway: c.gateway || c.Gateway || '' 
    }));
}

const addIpam = () => ipamConfigs.value.push({ subnet: '', gateway: '' });
const removeIpam = (idx) => ipamConfigs.value.splice(idx, 1);

const qosFields = ['delay', 'loss', 'rate', 'corrupt', 'reordering', 'limit', 'dport', 'ip'];

const save = async () => {
    saving.value = true;
    
    // Deep clone the settings to avoid modifying the form UI during processing
    const settings = JSON.parse(JSON.stringify(form.settings));

    // Process environment vars
    if (props.resource === 'host') {
        settings.environment = environmentText.value.split('\n')
            .map(line => line.trim())
            .filter(line => line && line.includes('='));
    }
    
    // Process IPAM
    if (props.resource === 'network') {
        settings.ipam = { 
            config: ipamConfigs.value
                .filter(c => c.subnet)
                .map(c => ({ subnet: c.subnet, gateway: c.gateway }))
        };
    }

    // SANITIZATION: Convert empty strings to null and ensure numbers are numbers
    Object.keys(settings).forEach(key => {
        const val = settings[key];
        if (val === '' || val === '---') {
            settings[key] = null;
        }
        // Ensure numeric fields are actually numbers
        if (['cpu', 'memory'].includes(key) && val !== null) {
            settings[key] = Number(val);
        }
    });

    const payload = {
        name: form.name,
        settings: settings
    };

    const res = props.isNew 
        ? await store.createProfile(props.resource, payload)
        : await store.updateProfile(props.resource, payload);
    
    if (res.success) {
        emit('saved');
    } else {
        // Show detailed error if available
        const msg = res.error?.error || res.error || 'Failed to save profile';
        alert(msg);
    }
    saving.value = false;
};
</script>
