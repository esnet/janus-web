<template>
  <div class="session-selector-pane">
    <div class="card border-0 shadow-sm p-4">
      <h5 class="font-weight-bold mb-1">
        <i class="fas fa-rocket mr-2 text-primary"></i>Launch GCS Setup Session
      </h5>
      <p class="text-muted small mb-4">
        Janus will launch a <code>dtnaas/globus-connect-server</code> container on the
        selected node. This container is used for the interactive endpoint setup step.
        After setup, a separate node container will be launched with the deployment key.
      </p>

      <!-- Node selection -->
      <div class="form-group">
        <label class="font-weight-bold small text-uppercase text-muted">
          Target Node <span class="text-danger">*</span>
        </label>
        <div v-if="loadingNodes" class="text-muted small">
          <i class="fas fa-spinner fa-spin mr-1"></i> Loading nodes...
        </div>
        <select v-else v-model="selectedNode" class="form-control" :disabled="launching">
          <option value="">— Select a node —</option>
          <option v-for="node in runningNodes" :key="node.name" :value="node.name">
            {{ node.name }}
            <span v-if="node.status === 1"> (active)</span>
          </option>
        </select>
        <small class="form-text text-muted">
          The Janus node where the GCS container will be launched.
        </small>
      </div>

      <!-- Display name -->
      <div class="form-group">
        <label class="font-weight-bold small text-uppercase text-muted">
          GCS Endpoint Display Name (optional)
        </label>
        <input
          v-model="displayName"
          type="text"
          class="form-control"
          placeholder="e.g. BNL-DTNAAS Endpoint"
          :disabled="launching"
        />
        <small class="form-text text-muted">
          Can also be set in the endpoint configuration step.
        </small>
      </div>

      <!-- Advanced: profile override -->
      <div class="form-group">
        <label class="font-weight-bold small text-uppercase text-muted">
          Profile
        </label>
        <input
          v-model="profile"
          type="text"
          class="form-control"
          :disabled="launching"
        />
        <small class="form-text text-muted">
          Janus profile to use for the GCS container. Default: <code>globus-gcs-test</code>
        </small>
      </div>

      <div v-if="error" class="alert alert-danger small py-2 mt-2">
        <i class="fas fa-exclamation-triangle mr-1"></i>{{ error }}
      </div>

      <div class="mt-3">
        <button
          class="btn btn-primary"
          :disabled="!selectedNode || launching"
          @click="launchAndProceed"
        >
          <span v-if="launching">
            <i class="fas fa-spinner fa-spin mr-1"></i> Launching container...
          </span>
          <span v-else>
            <i class="fas fa-play mr-1"></i> Launch GCS Container &amp; Continue
          </span>
        </button>
      </div>

      <!-- Launch progress -->
      <div v-if="launching" class="mt-3 alert alert-info small py-2">
        <i class="fas fa-info-circle mr-1"></i>
        Creating and starting the GCS setup container on <strong>{{ selectedNode }}</strong>...
        This may take a few seconds.
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue';
import api from '../../api';

const emit = defineEmits(['selected']);

const nodes = ref([]);
const loadingNodes = ref(false);
const selectedNode = ref('');
const displayName = ref('');
const profile = ref('globus-gcs-test');
const launching = ref(false);
const error = ref('');

const runningNodes = computed(() =>
  nodes.value.filter(n => n.status === 1)
);

onMounted(fetchNodes);

async function fetchNodes() {
  loadingNodes.value = true;
  try {
    const res = await api.getNodes();
    nodes.value = res.data.nodes || [];
  } catch (err) {
    error.value = 'Failed to load nodes.';
  } finally {
    loadingNodes.value = false;
  }
}

async function launchAndProceed() {
  error.value = '';
  launching.value = true;

  try {
    // Step 1: Create the GCS setup session via Janus Controller
    // entrypoint=/bin/bash keeps the container alive for interactive endpoint setup
    const createRes = await api.createSession({
      errors: [],
      instances: [selectedNode.value],
      image: 'dtnaas/globus-connect-server:debian-12-5.4.79',
      profile: profile.value,
      kwargs: {},
      remove_container: false,
      name: displayName.value || 'gcs-setup',
      entrypoint: '/bin/bash',
      arguments: '-c "sleep 86400"',
    });

    if (!createRes.data.status) {
      error.value = createRes.data.result?.error || 'Failed to create session.';
      return;
    }

    // Extract session ID from result
    const result = createRes.data.result;
    const sessionId = parseInt(Object.keys(result)[0]);

    // Step 2: Start the session
    const startRes = await api.startSession(sessionId);
    if (!startRes.data.status) {
      error.value = startRes.data.result?.error || 'Failed to start session.';
      return;
    }

    // Step 3: Extract container ID from the started session
    const sessionData = startRes.data.result[String(sessionId)];
    const servicesMap = sessionData?.services || {};
    let containerId = '';
    let actualNode = selectedNode.value;

    for (const [nodeName, svcs] of Object.entries(servicesMap)) {
      actualNode = nodeName;
      for (const svc of svcs) {
        if (svc.errors && svc.errors.length > 0) {
          error.value = `Container launch error: ${JSON.stringify(svc.errors[0])}`;
          return;
        }
        containerId = svc.container_id || '';
        break;
      }
      if (containerId) break;
    }

    if (!containerId) {
      error.value = 'Container launched but no container ID returned. Check the session.';
      return;
    }

    emit('selected', {
      sessionId,
      nodeName: actualNode,
      containerId,
      displayName: displayName.value.trim(),
    });

  } catch (err) {
    error.value = err.response?.data?.error || err.message || 'Failed to launch container.';
  } finally {
    launching.value = false;
  }
}
</script>

<style scoped>
.session-selector-pane .card {
  border-radius: 8px;
}
</style>
