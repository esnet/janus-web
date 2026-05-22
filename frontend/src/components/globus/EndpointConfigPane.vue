<template>
  <div class="endpoint-config-pane">
    <div class="card border-0 shadow-sm p-4 mb-3">
      <h5 class="font-weight-bold mb-1">
        <i class="fas fa-globe mr-2 text-primary"></i>Endpoint Configuration
      </h5>
      <!-- Endpoint ID override (shown if not auto-detected) -->
      <div
        v-if="cmdBuilt && !store.currentService?.globus_endpoint_id"
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
        into the terminal where you ran the command.
        After completion, click <strong>Collect Deployment Key</strong>.
      </div>

      <form @submit.prevent="buildCommand">
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
              :disabled="cmdBuilt"
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
              :disabled="cmdBuilt"
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
              :disabled="cmdBuilt"
            />
            <div v-if="errors.contact_email" class="invalid-feedback">{{ errors.contact_email }}</div>
          </div>
        </div>

        <div class="form-row">
          <div class="form-group col-md-6">
            <label class="font-weight-bold small text-uppercase text-muted">
              Owner (Globus Identity)
            </label>
            <input
              v-model="form.owner"
              type="text"
              class="form-control"
              placeholder="e.g. user@globusid.org"
              :disabled="cmdBuilt"
            />
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
              :disabled="cmdBuilt"
            />
          </div>
        </div>

        <div v-if="store.error" class="alert alert-danger small py-2">
          <i class="fas fa-exclamation-triangle mr-1"></i>{{ store.error }}
        </div>

        <div class="d-flex align-items-center mt-3" style="gap: 8px;" v-if="!cmdBuilt">
          <button
            type="button"
            class="btn btn-outline-secondary"
            @click="$emit('back')"
          >
            <i class="fas fa-arrow-left mr-1"></i> Back
          </button>
          <button type="submit" class="btn btn-primary" :disabled="loading">
            <span v-if="loading"><i class="fas fa-spinner fa-spin mr-1"></i> Building...</span>
            <span v-else><i class="fas fa-terminal mr-1"></i> Generate Setup Command</span>
          </button>
        </div>
      </form>

      <!-- Generated command to run -->
      <div v-if="cmdBuilt && generatedCmd" class="mt-3">
        <label class="font-weight-bold small text-uppercase text-muted">
          Run this command in your terminal:
        </label>
        <div class="input-group mb-2">
          <input
            :value="fullDockerCmd"
            type="text"
            class="form-control form-control-sm bg-dark text-white border-secondary"
            readonly
            style="font-family: monospace; font-size: 0.8rem;"
            ref="cmdInput"
          />
          <div class="input-group-append">
            <button class="btn btn-sm btn-outline-secondary" @click="copyCmd" title="Copy">
              <i class="fas" :class="copied ? 'fa-check text-success' : 'fa-copy'"></i>
            </button>
          </div>
        </div>
        <small class="text-muted">
          The command will print a Globus Auth URL. Open it, authenticate, and paste the code back into the terminal.
        </small>

        <div class="d-flex align-items-center mt-3" style="gap: 8px;">
          <button
            class="btn btn-outline-secondary btn-sm"
            @click="cmdBuilt = false; generatedCmd = ''"
          >
            <i class="fas fa-edit mr-1"></i> Edit
          </button>
          <button
            class="btn btn-warning"
            :disabled="collectingKey"
            @click="collectDeploymentKey"
          >
            <span v-if="collectingKey">
              <i class="fas fa-spinner fa-spin mr-1"></i> Collecting key...
            </span>
            <span v-else>
              <i class="fas fa-key mr-1"></i> Collect Deployment Key
            </span>
          </button>
        </div>
        <small class="text-muted d-block mt-1">
          Click after the terminal command completes successfully.
        </small>
      </div>
    </div>

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
import { reactive, ref, computed } from 'vue';
import { useGlobusServiceStore } from '../../stores/globusServiceStore';
import api from '../../api';

const emit = defineEmits(['next', 'back']);
const store = useGlobusServiceStore();

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

const errors = reactive({
  display_name: '',
  organization: '',
  contact_email: '',
});

const loading = ref(false);
const cmdBuilt = ref(false);
const generatedCmd = ref('');
const collectingKey = ref(false);
const deploymentKeyCollected = ref(false);
const copied = ref(false);
const cmdInput = ref(null);

// Full docker exec command for the user to run
const containerName = computed(() => {
  const svc = store.currentService;
  if (!svc) return '<container-name>';
  // Janus container naming: janus-<profile>-<session_id>-1
  return `janus-globus-gcs-test-${svc.session_id}-1`;
});

const fullDockerCmd = computed(() =>
  `docker exec -it ${containerName.value} bash -c "${generatedCmd.value}"`
);

function validate() {
  let valid = true;
  errors.display_name = '';
  errors.organization = '';
  errors.contact_email = '';

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
  return valid;
}

async function buildCommand() {
  if (!validate()) return;
  loading.value = true;
  store.error = null;
  try {
    const res = await api.getEndpointSetupCmd(store.currentService.id, { ...form });
    generatedCmd.value = res.data.cmd;
    cmdBuilt.value = true;
  } catch (err) {
    store.error = err.response?.data?.error || 'Failed to build command.';
  } finally {
    loading.value = false;
  }
}

async function copyCmd() {
  try {
    await navigator.clipboard.writeText(fullDockerCmd.value);
    copied.value = true;
    setTimeout(() => { copied.value = false; }, 2000);
  } catch {
    if (cmdInput.value) cmdInput.value.select();
  }
}

async function collectDeploymentKey() {
  collectingKey.value = true;
  store.error = null;
  try {
    const res = await api.fetchGlobusDeploymentKey(
      store.currentService.id,
      { deployment_key_path: form.deployment_key_path }
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
</script>
