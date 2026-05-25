<template>
  <div class="storage-gateway-pane">

    <!-- Step 4: Storage Gateway creation via service account REST API -->
    <div class="card border-0 shadow-sm p-4 mb-3">
      <h5 class="font-weight-bold mb-1">
        <i class="fas fa-hdd mr-2 text-info"></i>Step 4 — Create Storage Gateway
      </h5>
      <p class="text-muted small mb-2">
        Define a storage gateway connecting your GCS endpoint to a storage backend.
        The gateway is created via the Globus REST API using the Janus service account —
        no interactive GCS login is required.
      </p>
      <div class="alert alert-info small py-2 mb-4">
        <i class="fas fa-info-circle mr-1"></i>
        The endpoint must have been set up with <code>--owner &lt;service-account&gt;</code>
        (done automatically by the endpoint setup command) for this to succeed.
      </div>

      <form @submit.prevent="submit">
        <div class="form-row">
          <div class="form-group col-md-6">
            <label class="font-weight-bold small text-uppercase text-muted">
              Display Name <span class="text-danger">*</span>
            </label>
            <input
              v-model="form.display_name"
              type="text"
              class="form-control"
              :class="{ 'is-invalid': errors.display_name }"
              placeholder="e.g. BNL DTNAAS Gateway"
              :disabled="store.loading"
            />
            <div v-if="errors.display_name" class="invalid-feedback">{{ errors.display_name }}</div>
          </div>
          <div class="form-group col-md-6">
            <label class="font-weight-bold small text-uppercase text-muted">
              Connector Type <span class="text-danger">*</span>
            </label>
            <select
              v-model="form.connector"
              class="form-control"
              :class="{ 'is-invalid': errors.connector }"
              :disabled="store.loading"
            >
              <option value="">— Select —</option>
              <option value="posix">POSIX (local filesystem)</option>
              <option value="s3">Amazon S3</option>
              <option value="google-cloud-storage">Google Cloud Storage</option>
              <option value="azure-blob">Azure Blob Storage</option>
              <option value="blackpearl">Spectra BlackPearl</option>
              <option value="box">Box</option>
              <option value="ceph">Ceph</option>
              <option value="irods">iRODS</option>
            </select>
            <div v-if="errors.connector" class="invalid-feedback">{{ errors.connector }}</div>
          </div>
        </div>

        <div class="form-row">
          <div class="form-group col-md-6">
            <label class="font-weight-bold small text-uppercase text-muted">
              Allowed Domains
            </label>
            <input
              v-model="form.allowed_domains"
              type="text"
              class="form-control"
              placeholder="e.g. es.net (comma-separated)"
              :disabled="store.loading"
            />
            <small class="form-text text-muted">
              Restrict to users from these Globus Auth domains (comma-separated).
            </small>
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
              <i class="fas fa-spinner fa-spin mr-1"></i> Creating gateway...
            </span>
            <span v-else>
              <i class="fas fa-play mr-1"></i> Create Storage Gateway
            </span>
          </button>
        </div>
      </form>
    </div>

    <!-- Success -->
    <div
      v-if="store.currentService?.status === 'gateway_configured'"
      class="alert alert-success mt-3 d-flex align-items-center"
    >
      <i class="fas fa-check-circle fa-lg mr-3"></i>
      <div>
        <strong>Storage gateway created successfully!</strong>
        <div v-if="gatewayId" class="small mt-1">
          Gateway ID: <code>{{ gatewayId }}</code>
        </div>
        <button class="btn btn-success btn-sm mt-2" @click="$emit('next')">
          <i class="fas fa-arrow-right mr-1"></i> Continue to Collections
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { reactive, ref, computed } from 'vue';
import { useGlobusServiceStore } from '../../stores/globusServiceStore';

const emit = defineEmits(['next', 'back']);
const store = useGlobusServiceStore();

const form = reactive({
  display_name: '',
  connector: '',
  allowed_domains: '',
});

const errors = reactive({
  display_name: '',
  connector: '',
});

const gatewayId = computed(
  () => store.currentService?.config_data?.storage_gateway?.id || ''
);

function validate() {
  let valid = true;
  errors.display_name = '';
  errors.connector = '';

  if (!form.display_name.trim()) {
    errors.display_name = 'Display name is required.';
    valid = false;
  }
  if (!form.connector) {
    errors.connector = 'Please select a connector type.';
    valid = false;
  }
  return valid;
}

async function submit() {
  if (!validate()) return;
  store.error = null;

  const config = {
    display_name: form.display_name.trim(),
    connector: form.connector,
    allowed_domains: form.allowed_domains.trim()
      ? form.allowed_domains.split(',').map(d => d.trim()).filter(Boolean)
      : [],
  };
  await store.createGateway(config);
}
</script>
