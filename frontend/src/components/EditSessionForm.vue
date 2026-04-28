<template>
  <div class="card shadow-sm border-0 animated fadeIn">
    <div class="card-header bg-white py-3 border-bottom d-flex justify-content-between align-items-center">
      <h5 class="mb-0 font-weight-bold">
        <i class="fas fa-edit mr-2 text-primary"></i> Edit Session: <span class="text-muted">#{{ session.id }}</span>
      </h5>
      <button class="btn btn-sm btn-light border" @click="$emit('cancel')">
        <i class="fas fa-times mr-1"></i> Cancel
      </button>
    </div>
    <div class="card-body p-4">
      <form @submit.prevent="save(false)">
        
        <!-- Global Settings -->
        <div class="row mb-4">
          <div class="col-md-4">
            <label class="small font-weight-bold text-uppercase text-muted mb-1">Session Name</label>
            <input v-model="form.name" type="text" class="form-control" placeholder="e.g. data-processing">
          </div>
          <div class="col-md-4">
            <label class="small font-weight-bold text-uppercase text-muted mb-1">Container Image</label>
            <div class="input-group">
                <select v-model="form.image" class="custom-select" required>
                    <option value="" disabled>Select image...</option>
                    <option v-for="img in sessionStore.images" :key="img.name" :value="img.name">
                        {{ img.name }}
                    </option>
                </select>
                <div class="input-group-append">
                    <input type="text" v-model="form.imageTag" class="form-control" style="width: 80px" placeholder="latest">
                </div>
            </div>
          </div>
          <div class="col-md-4">
            <label class="small font-weight-bold text-uppercase text-muted mb-1">Container Profile</label>
            <select v-model="form.profile" class="custom-select" required>
                <option v-for="p in profileStore.profiles" :key="p.name" :value="p.name">
                    {{ p.name }}
                </option>
            </select>
          </div>
        </div>

        <hr class="mb-4">

        <!-- Instances (Nodes) -->
        <div class="mb-4">
            <div class="d-flex justify-content-between align-items-center mb-3">
                <label class="small font-weight-bold text-uppercase text-muted mb-0">Target Endpoints & Clusters</label>
                <button type="button" class="btn btn-outline-success btn-sm" @click="addInstance">
                    <i class="fas fa-plus mr-1"></i> Add Instance
                </button>
            </div>
            
            <div v-for="(inst, index) in form.instances" :key="index" class="card bg-light border-0 mb-3 shadow-none">
                <div class="card-body p-3">
                    <div class="row align-items-end">
                        <div class="col-md-5">
                            <label class="small font-weight-bold text-muted mb-1">Target Node</label>
                            <select v-model="inst.name" class="custom-select custom-select-sm" required @change="onNodeChange(index)">
                                <option value="" disabled>Select node...</option>
                                <option v-for="n in endpointStore.nodes" :key="n.name" :value="n.name">
                                    {{ n.name }}
                                </option>
                            </select>
                        </div>
                        <div class="col-md-5" v-if="getClustersForNode(inst.name).length">
                            <label class="small font-weight-bold text-muted mb-1">Specific Cluster/Node</label>
                            <select v-model="inst.nodeName" class="custom-select custom-select-sm">
                                <option value="">Any available</option>
                                <option v-for="c in getClustersForNode(inst.name)" :key="c" :value="c">
                                    {{ c }}
                                </option>
                            </select>
                        </div>
                        <div class="col-md-2 text-right">
                            <button type="button" class="btn btn-outline-danger btn-sm" @click="removeInstance(index)" :disabled="form.instances.length === 1">
                                <i class="fas fa-trash"></i>
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <hr class="mb-4">

        <!-- Advanced Settings -->
        <div class="row mb-4">
            <div class="col-md-6">
                <label class="small font-weight-bold text-uppercase text-muted mb-1">SSH User (Optional)</label>
                <input v-model="form.sshUser" type="text" class="form-control form-control-sm" placeholder="e.g. root">
            </div>
            <div class="col-md-6">
                <div class="custom-control custom-checkbox mt-4">
                    <input type="checkbox" class="custom-control-input" v-model="form.removeContainer" id="edit-check-remove">
                    <label class="custom-control-label font-weight-bold small text-uppercase" for="edit-check-remove">Auto-Remove Container on Stop</label>
                </div>
            </div>
        </div>

        <div class="row mb-4">
            <div class="col-12">
                <label class="small font-weight-bold text-uppercase text-muted mb-1">Command Arguments</label>
                <input v-model="form.arguments" type="text" class="form-control form-control-sm" placeholder="e.g. --verbose --port 8080">
            </div>
        </div>

        <div class="alert alert-info py-2" v-if="session.state === 'STARTED'">
            <i class="fas fa-info-circle mr-2"></i> This session is currently <b>RUNNING</b>. Changes will not take effect until you click <b>"Apply Changes"</b>.
        </div>

        <div class="mt-4 pt-3 border-top d-flex justify-content-between">
          <button type="button" class="btn btn-light border" @click="$emit('cancel')">Cancel</button>
          <div>
              <button type="submit" class="btn btn-primary px-4 mr-2" :disabled="saving">
                <i class="fas mr-2" :class="saving ? 'fa-spinner fa-spin' : 'fa-save'"></i>
                Save Metadata
              </button>
              <button type="button" class="btn btn-success px-4" @click="save(true)" :disabled="saving">
                <i class="fas mr-2" :class="saving ? 'fa-spinner fa-spin' : 'fa-sync-alt'"></i>
                Save & Apply Changes
              </button>
          </div>
        </div>
      </form>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue';
import { useSessionStore } from '../stores/sessionStore';
import { useEndpointStore } from '../stores/endpointStore';
import { useProfileStore } from '../stores/profileStore';

const props = defineProps(['session']);
const emit = defineEmits(['saved', 'cancel']);
const sessionStore = useSessionStore();
const endpointStore = useEndpointStore();
const profileStore = useProfileStore();

const saving = ref(false);

// Extract initial state from session.data.request[0]
const req = props.session.data.request[0] || {};
const initialImage = req.image || '';
const [imgName, imgTag] = initialImage.split(':');

const form = reactive({
  name: props.session.name || '',
  image: imgName || '',
  imageTag: imgTag || 'latest',
  profile: req.profile || 'default',
  instances: req.instances.map(inst => {
      if (typeof inst === 'string') return { name: inst, nodeName: '' };
      return { name: inst.name, nodeName: inst.nodeName || '' };
  }),
  sshUser: req.kwargs?.USER_NAME || '',
  sshKey: req.kwargs?.PUBLIC_KEY || '',
  arguments: req.arguments || '',
  removeContainer: req.remove_container || false
});

onMounted(async () => {
  await Promise.all([
      sessionStore.fetchImages(),
      endpointStore.fetchNodes(),
      profileStore.fetchAll()
  ]);
});

const addInstance = () => {
    form.instances.push({ name: '', nodeName: '' });
};

const removeInstance = (idx) => {
    form.instances.splice(idx, 1);
};

const onNodeChange = (idx) => {
    form.instances[idx].nodeName = '';
};

const getClustersForNode = (nodeName) => {
    const node = endpointStore.nodes.find(n => n.name === nodeName);
    if (!node || !node.data || !node.data.cluster_nodes) return [];
    return node.data.cluster_nodes.map(cn => cn.name);
};

const save = async (apply = false) => {
  saving.value = true;
  
  const instances = form.instances.map(inst => {
      if (!inst.nodeName) return inst.name;
      return { name: inst.name, nodeName: inst.nodeName };
  });

  const payload = {
    name: form.name || null,
    image: `${form.image}:${form.imageTag || 'latest'}`,
    profile: form.profile,
    instances: instances,
    arguments: form.arguments || null,
    remove_container: form.removeContainer,
    kwargs: {}
  };

  if (form.sshUser) payload.kwargs.USER_NAME = form.sshUser;
  if (form.sshKey) payload.kwargs.PUBLIC_KEY = form.sshKey;
  
  const res = await sessionStore.updateSession(props.session.id, payload, apply);
  if (res.success) {
    emit('saved');
  } else {
    alert(res.error || 'Failed to update session');
  }
  saving.value = false;
};
</script>

<style scoped>
.animated {
    animation-duration: 0.3s;
    animation-fill-mode: both;
}
@keyframes fadeIn {
    from { opacity: 0; transform: translateY(10px); }
    to { opacity: 1; transform: translateY(0); }
}
.fadeIn {
    animation-name: fadeIn;
}
</style>
