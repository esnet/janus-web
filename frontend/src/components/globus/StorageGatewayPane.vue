<template>
  <div class="storage-gateway-pane">

    <!-- Step 5: Storage Gateway creation via service account REST API -->
    <div class="card border-0 shadow-sm p-4 mb-3">
      <h5 class="font-weight-bold mb-1">
        <i class="fas fa-hdd mr-2 text-info"></i>Step 5 — Create Storage Gateway
      </h5>
      <p class="text-muted small mb-2">
        Define a storage gateway connecting your GCS endpoint to a storage backend.
        The gateway is created via the Globus REST API using the Janus service account —
        no interactive GCS login is required.
      </p>
      <div class="alert alert-info small py-2 mb-4">
        <i class="fas fa-info-circle mr-1"></i>
        GCS Login (Step 4) must have been completed before creating a gateway.
      </div>

      <form @submit.prevent="submit">
        <!-- Display Name + Connector -->
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

        <!-- Allowed Domains + User Deny -->
        <div class="form-row">
          <div class="form-group col-md-6">
            <label class="font-weight-bold small text-uppercase text-muted">
              Allowed Domains
            </label>
            <input
              v-model="form.allowed_domains"
              type="text"
              class="form-control"
              placeholder="e.g. es.net, bnl.gov (comma-separated)"
              :disabled="store.loading"
            />
            <small class="form-text text-muted">
              Restrict to users from these Globus Auth domains. Leave blank to allow all.
            </small>
          </div>
          <div class="form-group col-md-6">
            <label class="font-weight-bold small text-uppercase text-muted">
              Deny Users
            </label>
            <input
              v-model="form.users_deny"
              type="text"
              class="form-control"
              placeholder="e.g. root (comma-separated)"
              :disabled="store.loading"
            />
            <small class="form-text text-muted">
              Local POSIX usernames to deny access (e.g. <code>root</code>).
            </small>
          </div>
        </div>

        <!-- Path Restrictions -->
        <div class="card border-light bg-light p-3 mb-3">
          <div class="font-weight-bold small text-uppercase text-muted mb-2">
            <i class="fas fa-folder-open mr-1"></i> Path Restrictions (optional)
          </div>
          <p class="text-muted small mb-2">
            Restrict which filesystem paths users can access through this gateway.
            Leave all fields blank to allow access to all paths.
          </p>
          <div class="form-row">
            <div class="form-group col-md-4">
              <label class="small font-weight-bold">Read-Write Paths</label>
              <input
                v-model="form.restrict_rw"
                type="text"
                class="form-control form-control-sm"
                placeholder="e.g. /work/data, /scratch"
                :disabled="store.loading"
              />
              <small class="form-text text-muted">Comma-separated paths with full access.</small>
            </div>
            <div class="form-group col-md-4">
              <label class="small font-weight-bold">Read-Only Paths</label>
              <input
                v-model="form.restrict_ro"
                type="text"
                class="form-control form-control-sm"
                placeholder="e.g. /data/shared"
                :disabled="store.loading"
              />
              <small class="form-text text-muted">Comma-separated paths with read-only access.</small>
            </div>
            <div class="form-group col-md-4">
              <label class="small font-weight-bold">Denied Paths</label>
              <input
                v-model="form.restrict_none"
                type="text"
                class="form-control form-control-sm"
                placeholder="e.g. / (deny root)"
                :disabled="store.loading"
              />
              <small class="form-text text-muted">Comma-separated paths to block entirely.</small>
            </div>
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
  users_deny: '',
  restrict_rw: '',    // read-write paths (comma-separated)
  restrict_ro: '',    // read-only paths (comma-separated)
  restrict_none: '',  // denied paths (comma-separated)
});

const errors = reactive({
  display_name: '',
  connector: '',
});

const gatewayId = computed(
  () => store.currentService?.config_data?.storage_gateway?.id || ''
);

function splitPaths(str) {
  return str.split(',').map(p => p.trim()).filter(Boolean);
}

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
  };

  // Allowed domains
  const domains = form.allowed_domains.trim()
    ? form.allowed_domains.split(',').map(d => d.trim()).filter(Boolean)
    : [];
  if (domains.length) config.allowed_domains = domains;

  // Users deny
  const deny = form.users_deny.trim()
    ? form.users_deny.split(',').map(u => u.trim()).filter(Boolean)
    : [];
  if (deny.length) config.users_deny = deny;

  // Path restrictions — only include if at least one field is filled
  const rw = splitPaths(form.restrict_rw);
  const ro = splitPaths(form.restrict_ro);
  const none = splitPaths(form.restrict_none);
  if (rw.length || ro.length || none.length) {
    config.restrict_paths = {
      read_write: rw,
      read: ro,
      none: none,
    };
  }

  await store.createGateway(config);
}
</script>
