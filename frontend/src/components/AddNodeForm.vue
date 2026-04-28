<template>
  <div class="card shadow-sm border-0 animated fadeIn">
    <div class="card-header bg-white py-3 border-bottom d-flex justify-content-between align-items-center">
      <h5 class="mb-0 font-weight-bold">
        <i class="fas fa-plus-circle mr-2 text-success"></i> Add New Endpoint
      </h5>
      <button class="btn btn-sm btn-light border" @click="$emit('cancel')">
        <i class="fas fa-times mr-1"></i> Cancel
      </button>
    </div>
    <div class="card-body p-4">
      <form @submit.prevent="save">
        <div class="row">
          <div class="col-md-6 mb-3">
            <label class="small font-weight-bold text-uppercase text-muted mb-1">Node Name</label>
            <input v-model="form.name" type="text" class="form-control" required placeholder="e.g. cluster-01">
          </div>
          <div class="col-md-6 mb-3">
            <label class="small font-weight-bold text-uppercase text-muted mb-1">Node URL</label>
            <input v-model="form.url" type="text" class="form-control" required placeholder="tcp://localhost:9001">
          </div>
        </div>

        <div class="row">
          <div class="col-md-6 mb-3">
            <label class="small font-weight-bold text-uppercase text-muted mb-1">Node Type</label>
            <select v-model="form.type" class="custom-select" required>
              <option value="" disabled>Select type...</option>
              <option v-for="(label, val) in store.nodeTypes" :key="val" :value="val">
                {{ label }}
              </option>
            </select>
          </div>
          <div class="col-md-6 mb-3">
            <label class="small font-weight-bold text-uppercase text-muted mb-1">Public URL (Optional)</label>
            <input v-model="form.public_url" type="text" class="form-control" placeholder="e.g. 192.168.1.10">
            <small class="text-muted">Used for direct container connectivity</small>
          </div>
        </div>

        <div class="mt-4 pt-3 border-top d-flex justify-content-between">
          <button type="button" class="btn btn-light border" @click="$emit('cancel')">Cancel</button>
          <button type="submit" class="btn btn-success px-5" :disabled="saving">
            <i class="fas mr-2" :class="saving ? 'fa-spinner fa-spin' : 'fa-check-circle'"></i>
            {{ saving ? 'Adding...' : 'Add Endpoint' }}
          </button>
        </div>
      </form>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue';
import { useEndpointStore } from '../stores/endpointStore';

const emit = defineEmits(['saved', 'cancel']);
const store = useEndpointStore();

const saving = ref(false);
const form = reactive({
  name: '',
  url: '',
  type: '',
  public_url: ''
});

onMounted(() => {
  store.fetchNodeTypes();
});

const save = async () => {
  saving.value = true;
  // Ensure type is an integer for the backend
  const payload = {
    ...form,
    type: parseInt(form.type)
  };
  
  const res = await store.addNode(payload);
  if (res.success) {
    emit('saved');
  } else {
    alert(res.error || 'Failed to add node');
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
