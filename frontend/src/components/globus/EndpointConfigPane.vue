<template>
  <div class="endpoint-config-pane">
    <div class="card border-0 shadow-sm p-4 mb-3">
      <h5 class="font-weight-bold mb-1">
        <i class="fas fa-globe mr-2 text-primary"></i>Endpoint Configuration
      </h5>

      <!-- Endpoint ID override (shown if not auto-detected after terminal run) -->
      <div
        v-if="terminalDone && !store.currentService?.globus_endpoint_id"
        class="alert alert-warning small py-2 mb-3"
      >
        <i class="fas fa-exclamation-triangle mr-1"></i>
        Endpoint ID not auto-detected. Paste it from the terminal output below:
        <div class="input-group mt-2">
          <input
            v-model="manualEndpointId"
            type="text"
            class="form-control form-control-sm"
            placeholder="e.g. ec6f1897-d2c8-4cb6-b085-2131008a5e21"
          />
          <div class="input-group-append">
            <button class="btn btn-sm btn-warning" @click="setEndpointId" :disabled="!manualEndpointId.trim()">
              Set ID
            </button>
          </div>
        </div>
      </div>

      <p class="text-muted small mb-1">
        Register your GCS endpoint with Globus by running
        <code>globus-connect-server endpoint setup</code> inside the container.
      </p>
      <div class="alert alert-info small py-2 mb-4">
        <i class="fas fa-info-circle mr-1"></i>
        <strong>Interactive step:</strong> This command prints a Globus Auth URL.
        Open it in your browser, authenticate, then paste the resulting code back
        into the terminal below. The deployment key will be collected automatically
        when the command completes.
      </div>

      <form @submit.prevent="buildAndRun" v-if="!terminalActive && !terminalDone">
        <div class="form-row">
          <div class="form-group col-md-8">
            <label class="font-weight-bold small text-uppercase text-muted">
              Display Name <span class="text-danger">*</span>
            </label>
            <input
              v-model="form.display_name"
              type="text"
              class="form-control"
              :class="{ 'is-invalid': errors.display_name }"
              placeholder="e.g. BNL-DTNAAS Endpoint"
            />
            <div v-if="errors.display_name" class="invalid-feedback">{{ errors.display_name }}</div>
          </div>
        </div>

        <div class="form-row">
          <div class="form-group col-md-6">
            <label class="font-weight-bold small text-uppercase text-muted">
              Organization <span class="text-danger">*</span>
            </label>
            <input
              v-model="form.organization"
              type="text"
              class="form-control"
              :class="{ 'is-invalid': errors.organization }"
              placeholder="e.g. ESNet"
            />
            <div v-if="errors.organization" class="invalid-feedback">{{ errors.organization }}</div>
          </div>
          <div class="form-group col-md-6">
            <label class="font-weight-bold small text-uppercase text-muted">
              Contact Email <span class="text-danger">*</span>
            </label>
            <input
              v-model="form.contact_email"
              type="email"
              class="form-control"
              :class="{ 'is-invalid': errors.contact_email }"
              placeholder="e.g. admin@example.org"
            />
            <div v-if="errors.contact_email" class="invalid-feedback">{{ errors.contact_email }}</div>
          </div>
        </div>

        <div class="form-row">
          <div class="form-group col-md-6">
            <label class="font-weight-bold small text-uppercase text-muted">
              Owner (Globus Identity) <span class="text-danger">*</span>
            </label>
            <input
              v-model="form.owner"
              type="text"
              class="form-control"
              :class="{ 'is-invalid': errors.owner }"
              placeholder="e.g. user@globusid.org"
            />
            <div v-if="errors.owner" class="invalid-feedback">{{ errors.owner }}</div>
            <small class="form-text text-muted">
              Your Globus username or email. The service account will take ownership automatically after setup.
            </small>
          </div>
          <div class="form-group col-md-6">
            <label class="font-weight-bold small text-uppercase text-muted">
              Project ID (optional)
            </label>
            <input
              v-model="form.project_id"
              type="text"
              class="form-control"
              placeholder="Leave blank to auto-create"
            />
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
          >
            <i class="fas fa-arrow-left mr-1"></i> Back
          </button>
          <button type="submit" class="btn btn-primary" :disabled="loading">
            <span v-if="loading"><i class="fas fa-spinner fa-spin mr-1"></i> Starting...</span>
            <span v-else><i class="fas fa-terminal mr-1"></i> Run Endpoint Setup</span>
          </button>
        </div>
      </form>

      <!-- Terminal is active or done — show status bar -->
      <div v-if="terminalActive || terminalDone" class="mt-2">
        <div class="d-flex align-items-center mb-2" style="gap: 8px;">
          <span v-if="terminalActive" class="badge badge-warning">
            <i class="fas fa-circle fa-xs mr-1"></i> Terminal active
          </span>
          <span v-else-if="terminalDone && !collectingKey && !deploymentKeyCollected" class="badge badge-secondary">
            <i class="fas fa-check mr-1"></i> Terminal closed
          </span>
          <span v-if="collectingKey" class="badge badge-info">
            <i class="fas fa-spinner fa-spin mr-1"></i> Collecting deployment key...
          </span>
          <button
            v-if="terminalActive"
            class="btn btn-sm btn-outline-danger"
            @click="stopTerminal"
          >
            <i class="fas fa-stop mr-1"></i> Disconnect
          </button>
          <button
            v-if="terminalDone && !deploymentKeyCollected && !collectingKey"
            class="btn btn-sm btn-warning"
            @click="collectDeploymentKey"
          >
            <i class="fas fa-key mr-1"></i> Collect Deployment Key
          </button>
          <button
            v-if="terminalDone"
            class="btn btn-sm btn-outline-secondary"
            @click="resetTerminal"
          >
            <i class="fas fa-redo mr-1"></i> Re-run
          </button>
        </div>
      </div>
    </div>

    <!-- In-wizard WebSocket terminal -->
    <CommandOutputPanel
      v-if="terminalActive || terminalOutput.length > 0"
      :lines="terminalOutput"
      :loading="terminalActive"
      :allow-input="terminalActive"
      height="280px"
      @clear="terminalOutput = []"
      @send-input="store.sendInteractiveInput($event)"
    />

    <!-- Success state -->
    <div
      v-if="deploymentKeyCollected"
      class="alert alert-success mt-3 d-flex align-items-center"
    >
      <i class="fas fa-check-circle fa-lg mr-3"></i>
      <div>
        <strong>Deployment key collected!</strong>
        <div v-if="store.currentService?.globus_endpoint_id" class="small mt-1">
          Endpoint ID: <code>{{ store.currentService.globus_endpoint_id }}</code>
        </div>
        <div class="small text-muted mt-1">
          The deployment key is stored and will be used when launching the node container.
        </div>
        <button class="btn btn-success btn-sm mt-2" @click="$emit('next')">
          <i class="fas fa-arrow-right mr-1"></i> Continue to Node Setup
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { reactive, ref, onUnmounted } from 'vue';
import { useGlobusServiceStore } from '../../stores/globusServiceStore';
import CommandOutputPanel from './CommandOutputPanel.vue';
import api from '../../api';

const emit = defineEmits(['next', 'back']);
const store = useGlobusServiceStore();

// Regex to extract endpoint ID from GCS CLI output
// Matches both:
//   "Endpoint ID:  ec6f1897-..."   (from `endpoint show`)
//   "Created endpoint ec6f1897-..." (from `endpoint setup`)
const ENDPOINT_ID_RE = /(?:Endpoint\s+ID:|Created\s+endpoint)\s+([a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})/i;

const form = reactive({
  display_name: store.currentService?.display_name || '',
  organization: '',
  contact_email: '',
  owner: '',
  project_id: '',
  deployment_key_path: '/work/deployment-key.json',
  always_create_project: true,
});

const manualEndpointId = ref('');
const extractedEndpointId = ref('');  // endpoint ID parsed from terminal output
const loading = ref(false);
const terminalActive = ref(false);
const terminalDone = ref(false);
const terminalOutput = ref([]);
const collectingKey = ref(false);
const deploymentKeyCollected = ref(false);

const errors = reactive({
  display_name: '',
  organization: '',
  contact_email: '',
  owner: '',
});

async function setEndpointId() {
  if (!manualEndpointId.value.trim() || !store.currentService) return;
  store.error = null;
  try {
    const res = await api.setGlobusEndpointId(store.currentService.id, manualEndpointId.value.trim());
    if (res.data.service) {
      store.currentService = res.data.service;
    }
    manualEndpointId.value = '';
  } catch (err) {
    store.error = err.response?.data?.error || 'Failed to set endpoint ID.';
  }
}

function validate() {
  let valid = true;
  errors.display_name = '';
  errors.organization = '';
  errors.contact_email = '';
  errors.owner = '';

  if (!form.display_name.trim()) {
    errors.display_name = 'Display name is required.';
    valid = false;
  }
  if (!form.organization.trim()) {
    errors.organization = 'Organization is required.';
    valid = false;
  }
  if (!form.contact_email.trim()) {
    errors.contact_email = 'Contact email is required.';
    valid = false;
  } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.contact_email)) {
    errors.contact_email = 'Please enter a valid email address.';
    valid = false;
  }
  if (!form.owner.trim()) {
    errors.owner = 'Globus identity (owner) is required.';
    valid = false;
  }
  return valid;
}

async function buildAndRun() {
  if (!validate()) return;
  loading.value = true;
  store.error = null;
  try {
    // Get the command string from the backend
    const res = await api.getEndpointSetupCmd(store.currentService.id, { ...form });
    const cmd = res.data.cmd;

    // Open the interactive WebSocket terminal
    terminalOutput.value = [];
    terminalActive.value = true;
    terminalDone.value = false;

    const ws = store.connectInteractive(store.currentService.id);

    // Route all store output to our local terminal output array
    const origAppend = store.appendOutput.bind(store);
    store.appendOutput = (type, text) => {
      terminalOutput.value.push({ type, text, timestamp: new Date().toISOString() });

      // Auto-extract endpoint ID from streaming output
      if ((type === 'stdout' || type === 'info') && text) {
        const match = text.match(ENDPOINT_ID_RE);
        if (match) {
          const extractedId = match[1];
          // Store locally so collectDeploymentKey can pass it as a hint
          // even if the setGlobusEndpointId API call hasn't resolved yet
          if (!extractedEndpointId.value) {
            extractedEndpointId.value = extractedId;
          }
          if (store.currentService && !store.currentService.globus_endpoint_id) {
            api.setGlobusEndpointId(store.currentService.id, extractedId)
              .then(r => {
                if (r.data.service) store.currentService = r.data.service;
              })
              .catch(() => {});
          }
        }
      }
    };

    ws.addEventListener('open', () => {
      terminalOutput.value.push({ type: 'info', text: `Running: ${cmd}` });
      terminalOutput.value.push({ type: 'info', text: '─'.repeat(60) });
      store.sendInteractiveExec(cmd);
    });

    ws.addEventListener('message', (event) => {
      try {
        const msg = JSON.parse(event.data);
        if (msg.type === 'done') {
          // WebSocket done — auto-trigger deployment key collection
          terminalActive.value = false;
          terminalDone.value = true;
          store.appendOutput = origAppend;
          collectDeploymentKey();
        }
      } catch (_) {}
    });

    ws.addEventListener('close', () => {
      terminalActive.value = false;
      terminalDone.value = true;
      store.appendOutput = origAppend;
    });

    ws.addEventListener('error', () => {
      terminalActive.value = false;
      terminalDone.value = true;
      store.appendOutput = origAppend;
      terminalOutput.value.push({ type: 'error', text: 'WebSocket error. Check console.' });
    });

  } catch (err) {
    store.error = err.response?.data?.error || 'Failed to build command.';
  } finally {
    loading.value = false;
  }
}

async function collectDeploymentKey() {
  if (collectingKey.value) return;
  collectingKey.value = true;
  store.error = null;
  try {
    // Pass the endpoint ID hint so the backend can derive gcs_address
    // even if the setGlobusEndpointId call hasn't completed yet
    const payload = { deployment_key_path: form.deployment_key_path };
    const idHint = extractedEndpointId.value || store.currentService?.globus_endpoint_id;
    if (idHint) payload.endpoint_id = idHint;

    const res = await api.fetchGlobusDeploymentKey(
      store.currentService.id,
      payload
    );
    if (res.data.success) {
      store.currentService = res.data.service;
      deploymentKeyCollected.value = true;
    } else {
      store.error = res.data.output || 'Failed to collect deployment key. Make sure the setup command completed successfully.';
    }
  } catch (err) {
    store.error = err.response?.data?.error || 'Failed to collect deployment key.';
  } finally {
    collectingKey.value = false;
  }
}

function stopTerminal() {
  store.disconnectInteractive();
  terminalActive.value = false;
  terminalDone.value = true;
}

function resetTerminal() {
  terminalOutput.value = [];
  terminalActive.value = false;
  terminalDone.value = false;
  deploymentKeyCollected.value = false;
  extractedEndpointId.value = '';
  store.error = null;
}

onUnmounted(() => {
  if (terminalActive.value) store.disconnectInteractive();
});
</script>
