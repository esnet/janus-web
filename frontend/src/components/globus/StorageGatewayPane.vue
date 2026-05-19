<template>
  <div class="storage-gateway-pane">

    <!-- Step 4a: GCS Login (required before gateway creation) -->
    <div class="card border-0 shadow-sm p-4 mb-3">
      <h5 class="font-weight-bold mb-1">
        <i class="fas fa-sign-in-alt mr-2 text-warning"></i>Step 4a — Authenticate GCS Node
      </h5>
      <p class="text-muted small mb-2">
        Before creating a storage gateway, you must authenticate the GCS node with Globus.
        This runs <code>globus-connect-server login &lt;endpoint-id&gt;</code> interactively.
      </p>
      <div class="alert alert-info small py-2 mb-3">
        <i class="fas fa-info-circle mr-1"></i>
        <strong>Interactive step:</strong> A Globus Auth URL will be printed. Open it,
        authorize, then paste the code into the terminal below.
      </div>

      <!-- Endpoint ID missing — allow inline paste -->
      <div v-if="!store.currentService?.globus_endpoint_id" class="alert alert-warning small py-2 mb-3">
        <i class="fas fa-exclamation-triangle mr-1"></i>
        <strong>Endpoint ID not set.</strong>
        Paste the endpoint ID from your terminal output (printed by <code>globus-connect-server endpoint setup</code>):
        <div class="input-group mt-2">
          <input
            v-model="manualEndpointId"
            type="text"
            class="form-control form-control-sm"
            placeholder="e.g. ec6f1897-d2c8-4cb6-b085-2131008a5e21"
          />
          <div class="input-group-append">
            <button
              class="btn btn-sm btn-warning"
              :disabled="!manualEndpointId.trim() || settingEndpointId"
              @click="setEndpointId"
            >
              <span v-if="settingEndpointId"><i class="fas fa-spinner fa-spin mr-1"></i></span>
              Set ID
            </button>
          </div>
        </div>
      </div>

      <div class="d-flex align-items-center" style="gap: 8px;">
        <button
          class="btn btn-warning"
          :disabled="loginRunning || !store.currentService?.globus_endpoint_id"
          @click="startLogin"
        >
          <i class="fas fa-terminal mr-1"></i>
          {{ loginRunning ? 'Session active...' : 'Run GCS Login' }}
        </button>
        <button
          v-if="loginRunning"
          class="btn btn-outline-danger"
          @click="stopLogin"
        >
          <i class="fas fa-stop mr-1"></i> Disconnect
        </button>
      </div>

      <!-- Optional: set-owner step -->
      <div class="mt-3 border-top pt-3">
        <label class="font-weight-bold small text-uppercase text-muted">
          Transfer Ownership to Service Account (optional but recommended)
        </label>
        <div class="input-group input-group-sm mt-1" style="max-width: 520px;">
          <input
            v-model="serviceAccountId"
            type="text"
            class="form-control"
            placeholder="e.g. 68c19eed-8872-4107-b85c-e11be12db9ad@clients.auth.globus.org"
            :disabled="loginRunning"
          />
          <div class="input-group-append">
            <button
              class="btn btn-outline-secondary"
              :disabled="!serviceAccountId.trim() || loginRunning"
              @click="runSetOwner"
            >
              Set Owner
            </button>
          </div>
        </div>
        <small class="form-text text-muted">
          Required before gateway creation if using a service account for programmatic management.
        </small>
      </div>
    </div>

    <!-- Interactive terminal (shared for login + set-owner) -->
    <CommandOutputPanel
      v-if="loginRunning || loginOutput.length > 0"
      :lines="loginOutput"
      :loading="false"
      :allow-input="loginRunning"
      height="220px"
      @clear="loginOutput = []"
      @send-input="store.sendInteractiveInput($event)"
    />

    <!-- Step 4b: Storage Gateway creation -->
    <div class="card border-0 shadow-sm p-4 mb-3 mt-3">
      <h5 class="font-weight-bold mb-1">
        <i class="fas fa-hdd mr-2 text-info"></i>Step 4b — Create Storage Gateway
      </h5>
      <p class="text-muted small mb-4">
        Define a storage gateway connecting your GCS endpoint to a storage backend.
        Runs <code>globus-connect-server storage-gateway create</code> inside the container.
      </p>

      <form @submit.prevent="submit">
        <div class="form-row">
          <div class="form-group col-md-6">
            <label class="font-weight-bold small text-uppercase text-muted">
              Gateway Name <span class="text-danger">*</span>
            </label>
            <input
              v-model="form.gateway_name"
              type="text"
              class="form-control"
              :class="{ 'is-invalid': errors.gateway_name }"
              placeholder="e.g. BNL DTNAAS Gateway"
              :disabled="store.loading"
            />
            <div v-if="errors.gateway_name" class="invalid-feedback">{{ errors.gateway_name }}</div>
          </div>
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
        </div>

        <div class="form-row">
          <div class="form-group col-md-4">
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
          <div class="form-group col-md-4">
            <label class="font-weight-bold small text-uppercase text-muted">
              Auth Domain
            </label>
            <input
              v-model="form.domain"
              type="text"
              class="form-control"
              placeholder="e.g. es.net"
              :disabled="store.loading"
            />
            <small class="form-text text-muted">Restrict to users from this Globus Auth domain.</small>
          </div>
          <div class="form-group col-md-4">
            <label class="font-weight-bold small text-uppercase text-muted">
              Deny Users
            </label>
            <input
              v-model="form.user_deny"
              type="text"
              class="form-control"
              placeholder="root (comma-separated)"
              :disabled="store.loading"
            />
            <small class="form-text text-muted">Local users to deny access (default: root).</small>
          </div>
        </div>

        <!-- Path restrictions -->
        <div class="form-group">
          <label class="font-weight-bold small text-uppercase text-muted">
            Path Restrictions
          </label>
          <div class="form-check mb-2">
            <input
              id="use-file"
              v-model="useRestrictFile"
              type="checkbox"
              class="form-check-input"
            />
            <label class="form-check-label small" for="use-file">
              Use a JSON file inside the container (recommended)
            </label>
          </div>

          <div v-if="useRestrictFile" class="input-group">
            <div class="input-group-prepend">
              <span class="input-group-text small">file:</span>
            </div>
            <input
              v-model="form.restrict_paths_file"
              type="text"
              class="form-control"
              placeholder="/work/path-restrictions.json"
              :disabled="store.loading"
            />
          </div>
          <small v-if="useRestrictFile" class="form-text text-muted">
            File format: <code>{"DATA_TYPE":"path_restrictions#1.0.0","read_write":["/data/ESnet"]}</code>
          </small>

          <div v-else>
            <div
              v-for="(path, idx) in form.restrict_paths"
              :key="idx"
              class="input-group mb-2"
            >
              <input
                v-model="form.restrict_paths[idx]"
                type="text"
                class="form-control"
                placeholder="e.g. /data/shared"
                :disabled="store.loading"
              />
              <div class="input-group-append">
                <button type="button" class="btn btn-outline-danger" @click="removePath(idx)">
                  <i class="fas fa-times"></i>
                </button>
              </div>
            </div>
            <button type="button" class="btn btn-sm btn-outline-secondary" @click="addPath">
              <i class="fas fa-plus mr-1"></i> Add Path
            </button>
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

    <!-- Gateway creation output -->
    <CommandOutputPanel
      v-if="store.commandOutput.length > 0 || store.loading"
      :lines="store.commandOutput"
      :loading="store.loading"
      height="220px"
      @clear="store.clearOutput()"
    />

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
import { reactive, ref, computed, onUnmounted } from 'vue';
import { useGlobusServiceStore } from '../../stores/globusServiceStore';
import CommandOutputPanel from './CommandOutputPanel.vue';
import api from '../../api';

const emit = defineEmits(['next', 'back']);
const store = useGlobusServiceStore();

// Login state
const loginRunning = ref(false);
const loginOutput = ref([]);
const serviceAccountId = ref('');

// Endpoint ID manual entry (when auto-extraction failed)
const manualEndpointId = ref('');
const settingEndpointId = ref(false);

async function setEndpointId() {
  if (!manualEndpointId.value.trim() || !store.currentService) return;
  settingEndpointId.value = true;
  store.error = null;
  try {
    const res = await api.setGlobusEndpointId(store.currentService.id, manualEndpointId.value.trim());
    if (res.data.service) {
      store.currentService = res.data.service;
    }
    manualEndpointId.value = '';
  } catch (err) {
    store.error = err.response?.data?.error || 'Failed to set endpoint ID.';
  } finally {
    settingEndpointId.value = false;
  }
}

// Gateway form
const useRestrictFile = ref(true);
const form = reactive({
  gateway_name: '',
  display_name: '',
  connector: '',
  domain: '',
  user_deny: 'root',
  restrict_paths_file: '/work/path-restrictions.json',
  restrict_paths: [],
});

const errors = reactive({
  gateway_name: '',
  display_name: '',
  connector: '',
});

const gatewayId = computed(
  () => store.currentService?.config_data?.storage_gateway?.id || ''
);

// ---- Login helpers ----
async function startLogin() {
  loginOutput.value = [];
  try {
    const res = await api.getGlobusLoginCmd(store.currentService.id);
    const cmd = res.data.cmd;
    loginOutput.value.push({ type: 'info', text: `Command: ${cmd}` });
    loginOutput.value.push({ type: 'info', text: '─'.repeat(60) });
    loginOutput.value.push({ type: 'info', text: 'Starting interactive session...' });

    loginRunning.value = true;
    const ws = store.connectInteractive(store.currentService.id);

    // Override the store output to go to loginOutput
    const origAppend = store.appendOutput.bind(store);
    store.appendOutput = (type, text) => {
      loginOutput.value.push({ type, text, timestamp: new Date().toISOString() });
    };

    ws.addEventListener('open', () => {
      store.sendInteractiveExec(cmd);
    });
    ws.addEventListener('close', () => {
      loginRunning.value = false;
      store.appendOutput = origAppend;
    });
  } catch (err) {
    loginOutput.value.push({
      type: 'error',
      text: err.response?.data?.error || 'Failed to get login command.',
    });
  }
}

async function runSetOwner() {
  if (!serviceAccountId.value.trim()) return;
  try {
    const res = await api.setGlobusEndpointOwner(store.currentService.id, serviceAccountId.value.trim());
    const cmd = res.data.cmd;
    loginOutput.value.push({ type: 'info', text: `Running: ${cmd}` });
    if (loginRunning.value) {
      store.sendInteractiveExec(cmd);
    } else {
      loginOutput.value.push({
        type: 'info',
        text: 'Start an interactive session first, then run set-owner.',
      });
    }
  } catch (err) {
    loginOutput.value.push({
      type: 'error',
      text: err.response?.data?.error || 'Failed to get set-owner command.',
    });
  }
}

function stopLogin() {
  store.disconnectInteractive();
  loginRunning.value = false;
}

// ---- Gateway form helpers ----
function addPath() {
  form.restrict_paths.push('');
}
function removePath(idx) {
  form.restrict_paths.splice(idx, 1);
}

function validate() {
  let valid = true;
  errors.gateway_name = '';
  errors.display_name = '';
  errors.connector = '';

  if (!form.gateway_name.trim()) {
    errors.gateway_name = 'Gateway name is required.';
    valid = false;
  }
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
  store.clearOutput();
  const config = {
    gateway_name: form.gateway_name.trim(),
    display_name: form.display_name.trim(),
    connector: form.connector,
    domain: form.domain.trim(),
    user_deny: form.user_deny.trim(),
    restrict_paths_file: useRestrictFile.value ? form.restrict_paths_file.trim() : '',
    restrict_paths: useRestrictFile.value ? [] : form.restrict_paths.filter(p => p.trim()),
  };
  await store.createGateway(config);
}

onUnmounted(() => {
  if (loginRunning.value) store.disconnectInteractive();
});
</script>
