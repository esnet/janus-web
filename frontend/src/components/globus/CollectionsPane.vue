<template>
  <div class="collections-pane">
    <div class="card border-0 shadow-sm p-4 mb-3">
      <h5 class="font-weight-bold mb-1">
        <i class="fas fa-folder-open mr-2 text-warning"></i>Collections
      </h5>
      <p class="text-muted small mb-4">
        Create a mapped or guest collection on your storage gateway.
        Runs <code>globus-connect-server collection create</code> inside the container.
        You can create multiple collections (e.g. one read-only, one read-write).
      </p>

      <!-- Created collections list -->
      <div v-if="createdCollections.length > 0" class="mb-4">
        <h6 class="font-weight-bold small text-uppercase text-muted mb-2">
          <i class="fas fa-check-circle text-success mr-1"></i>Created Collections
        </h6>
        <div
          v-for="col in createdCollections"
          :key="col.id || col.display_name"
          class="d-flex align-items-center p-2 mb-2 bg-light rounded"
        >
          <i class="fas fa-folder text-warning mr-2"></i>
          <div>
            <strong class="small">{{ col.display_name }}</strong>
            <span class="badge ml-2" :class="col.read_write ? 'badge-warning' : 'badge-secondary'">
              {{ col.read_write ? 'read-write' : 'read-only' }}
            </span>
            <div class="text-muted" style="font-size: 0.75rem;">
              <span v-if="col.id">ID: <code>{{ col.id }}</code> &mdash; </span>
              Path: <code>{{ col.base_path }}</code>
            </div>
          </div>
        </div>
      </div>

      <form @submit.prevent="submit">
        <div class="form-row">
          <div class="form-group col-md-8">
            <label class="font-weight-bold small text-uppercase text-muted">
              Collection Display Name <span class="text-danger">*</span>
            </label>
            <input
              v-model="form.display_name"
              type="text"
              class="form-control"
              :class="{ 'is-invalid': errors.display_name }"
              placeholder='e.g. "ESnet read-only Collection at BNL DTNAAS"'
              :disabled="store.loading"
            />
            <div v-if="errors.display_name" class="invalid-feedback">{{ errors.display_name }}</div>
          </div>
          <div class="form-group col-md-4">
            <label class="font-weight-bold small text-uppercase text-muted">
              Collection Type
            </label>
            <select v-model="form.collection_type" class="form-control" :disabled="store.loading">
              <option value="mapped">Mapped</option>
              <option value="guest">Guest</option>
            </select>
          </div>
        </div>

        <div class="form-row">
          <div class="form-group col-md-8">
            <label class="font-weight-bold small text-uppercase text-muted">
              Storage Gateway ID <span class="text-danger">*</span>
            </label>
            <input
              v-model="form.storage_gateway_id"
              type="text"
              class="form-control"
              :class="{ 'is-invalid': errors.storage_gateway_id }"
              placeholder="UUID of the storage gateway"
              :disabled="store.loading"
            />
            <div v-if="errors.storage_gateway_id" class="invalid-feedback">{{ errors.storage_gateway_id }}</div>
            <small v-if="autoGatewayId" class="form-text text-success">
              <i class="fas fa-check-circle mr-1"></i>Auto-filled from previous step.
            </small>
          </div>
          <div class="form-group col-md-4">
            <label class="font-weight-bold small text-uppercase text-muted">
              Base Path <span class="text-danger">*</span>
            </label>
            <input
              v-model="form.base_path"
              type="text"
              class="form-control"
              :class="{ 'is-invalid': errors.base_path }"
              placeholder="e.g. /data/ESnet/"
              :disabled="store.loading"
            />
            <div v-if="errors.base_path" class="invalid-feedback">{{ errors.base_path }}</div>
          </div>
        </div>

        <div class="form-row">
          <div class="form-group col-md-6">
            <label class="font-weight-bold small text-uppercase text-muted">Description</label>
            <input
              v-model="form.description"
              type="text"
              class="form-control"
              placeholder="e.g. ESnet read-only Collection at BNL DTNAAS"
              :disabled="store.loading"
            />
          </div>
          <div class="form-group col-md-3">
            <label class="font-weight-bold small text-uppercase text-muted">Organization</label>
            <input
              v-model="form.organization"
              type="text"
              class="form-control"
              placeholder="e.g. ESnet"
              :disabled="store.loading"
            />
          </div>
          <div class="form-group col-md-3">
            <label class="font-weight-bold small text-uppercase text-muted">Keywords</label>
            <input
              v-model="form.keywords"
              type="text"
              class="form-control"
              placeholder="e.g. testing,dtn"
              :disabled="store.loading"
            />
          </div>
        </div>

        <!-- Sharing restrictions -->
        <div class="form-group">
          <label class="font-weight-bold small text-uppercase text-muted">
            Sharing Restrictions File (optional)
          </label>
          <div class="input-group">
            <div class="input-group-prepend">
              <span class="input-group-text small">file:</span>
            </div>
            <input
              v-model="form.sharing_restrict_paths_file"
              type="text"
              class="form-control"
              placeholder="e.g. /work/sharing-restrictions.json"
              :disabled="store.loading"
            />
          </div>
          <small class="form-text text-muted">
            Read-only example: <code>{"DATA_TYPE":"path_restrictions#1.0.0","read":["/"]}</code><br/>
            Read-write example: <code>{"DATA_TYPE":"path_restrictions#1.0.0","read_write":["/data/ESnet/write-testing/"]}</code>
          </small>
        </div>

        <!-- Anonymous writes -->
        <div class="form-group">
          <div class="custom-control custom-switch">
            <input
              id="anon-writes"
              v-model="form.enable_anonymous_writes"
              type="checkbox"
              class="custom-control-input"
              :disabled="store.loading"
            />
            <label class="custom-control-label" for="anon-writes">
              Enable anonymous writes
              <small class="text-muted ml-1">(adds <code>--enable-anonymous-writes</code>)</small>
            </label>
          </div>
        </div>

        <div v-if="store.error" class="alert alert-danger small py-2">
          <i class="fas fa-exclamation-triangle mr-1"></i>{{ store.error }}
        </div>

        <div class="d-flex align-items-center mt-3" style="gap: 8px;">
          <button
            type="button"
            class="btn btn-outline-secondary"
            @click="$emit('back')"
            :disabled="store.loading"
          >
            <i class="fas fa-arrow-left mr-1"></i> Back
          </button>
          <button
            type="submit"
            class="btn btn-primary"
            :disabled="store.loading"
          >
            <span v-if="store.loading">
              <i class="fas fa-spinner fa-spin mr-1"></i> Creating collection...
            </span>
            <span v-else>
              <i class="fas fa-plus mr-1"></i> Create Collection
            </span>
          </button>
          <button
            v-if="createdCollections.length > 0"
            type="button"
            class="btn btn-success"
            @click="$emit('finish')"
            :disabled="store.loading"
          >
            <i class="fas fa-flag-checkered mr-1"></i> Finish Setup
          </button>
        </div>
      </form>
    </div>

    <!-- Command output -->
    <CommandOutputPanel
      v-if="store.commandOutput.length > 0 || store.loading"
      :lines="store.commandOutput"
      :loading="store.loading"
      height="220px"
      @clear="store.clearOutput()"
    />

    <!-- Latest collection success -->
    <div v-if="lastCreatedCollection" class="alert alert-success mt-3 d-flex align-items-center">
      <i class="fas fa-check-circle fa-lg mr-3"></i>
      <div>
        <strong>Collection created successfully!</strong>
        <div v-if="lastCreatedCollection.id" class="small mt-1">
          Collection ID: <code>{{ lastCreatedCollection.id }}</code>
        </div>
        <div class="small text-muted">
          You can create additional collections or click <strong>Finish Setup</strong>.
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { reactive, ref, computed, onMounted } from 'vue';
import { useGlobusServiceStore } from '../../stores/globusServiceStore';
import CommandOutputPanel from './CommandOutputPanel.vue';

const emit = defineEmits(['back', 'finish']);
const store = useGlobusServiceStore();

const createdCollections = ref([]);
const lastCreatedCollection = ref(null);

const autoGatewayId = computed(
  () => store.currentService?.config_data?.storage_gateway?.id || ''
);

const form = reactive({
  display_name: '',
  storage_gateway_id: '',
  base_path: '/data/ESnet/',
  collection_type: 'mapped',
  description: '',
  organization: '',
  keywords: '',
  enable_anonymous_writes: false,
  sharing_restrict_paths_file: '',
});

const errors = reactive({
  display_name: '',
  storage_gateway_id: '',
  base_path: '',
});

onMounted(() => {
  if (autoGatewayId.value) {
    form.storage_gateway_id = autoGatewayId.value;
  }
});

function validate() {
  let valid = true;
  errors.display_name = '';
  errors.storage_gateway_id = '';
  errors.base_path = '';

  if (!form.display_name.trim()) {
    errors.display_name = 'Collection display name is required.';
    valid = false;
  }
  if (!form.storage_gateway_id.trim()) {
    errors.storage_gateway_id = 'Storage gateway ID is required.';
    valid = false;
  }
  if (!form.base_path.trim()) {
    errors.base_path = 'Base path is required.';
    valid = false;
  } else if (!form.base_path.startsWith('/')) {
    errors.base_path = 'Base path must start with /';
    valid = false;
  }
  return valid;
}

async function submit() {
  if (!validate()) return;
  store.clearOutput();
  lastCreatedCollection.value = null;

  const config = {
    display_name: form.display_name.trim(),
    storage_gateway_id: form.storage_gateway_id.trim(),
    base_path: form.base_path.trim(),
    collection_type: form.collection_type,
    description: form.description.trim(),
    organization: form.organization.trim(),
    keywords: form.keywords.trim(),
    enable_anonymous_writes: form.enable_anonymous_writes,
    sharing_restrict_paths_file: form.sharing_restrict_paths_file.trim(),
  };

  const result = await store.createCollection(config);
  if (result.success) {
    const collectionId = store.currentService?.config_data?.collection?.id || '';
    const created = {
      id: collectionId,
      display_name: form.display_name,
      base_path: form.base_path,
      read_write: form.enable_anonymous_writes,
    };
    createdCollections.value.push(created);
    lastCreatedCollection.value = created;
    // Reset form for another collection
    form.display_name = '';
    form.base_path = '/';
    form.description = '';
    form.keywords = '';
    form.enable_anonymous_writes = false;
    form.sharing_restrict_paths_file = '';
  }
}
</script>
