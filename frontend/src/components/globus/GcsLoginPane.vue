<template>
  <div class="gcs-login-pane">
    <div class="card border-0 shadow-sm p-4 mb-3">
      <h5 class="font-weight-bold mb-1">
        <i class="fas fa-sign-in-alt mr-2 text-warning"></i>GCS Login
      </h5>
      <p class="text-muted small mb-1">
        Authenticate the GCS Manager on the node container with your Globus identity.
        This populates the GCS Manager's role database, which is required before
        storage gateway and collection creation.
      </p>
      <div class="alert alert-info small py-2 mb-4">
        <i class="fas fa-info-circle mr-1"></i>
        <strong>Interactive step:</strong> The command below will print a Globus Auth URL.
        Open it in your browser, authenticate, then paste the resulting code back
        into the terminal.
        <span v-if="hasServiceIdentity">
          Ownership will then be transferred to the service account automatically.
        </span>
      </div>

      <!-- Pre-run: show Run button -->
      <div v-if="!terminalActive && !terminalDone" class="d-flex align-items-center" style="gap: 8px;">
        <button
          type="button"
          class="btn btn-outline-secondary"
          @click="$emit('back')"
        >
          <i class="fas fa-arrow-left mr-1"></i> Back
        </button>
        <button
          class="btn btn-warning"
          :disabled="loading"
          @click="runLogin"
        >
          <span v-if="loading"><i class="fas fa-spinner fa-spin mr-1"></i> Starting...</span>
          <span v-else><i class="fas fa-terminal mr-1"></i> Run GCS Login</span>
        </button>
      </div>

      <!-- Terminal active / done: show status bar -->
      <div v-if="terminalActive || terminalDone" class="mt-2">
        <div class="d-flex align-items-center mb-2" style="gap: 8px;">
          <span v-if="terminalActive" class="badge badge-warning">
            <i class="fas fa-circle fa-xs mr-1"></i> Terminal active
          </span>
          <span v-else-if="terminalDone && !loginComplete" class="badge badge-secondary">
            <i class="fas fa-check mr-1"></i> Terminal closed
          </span>
          <button
            v-if="terminalActive"
            class="btn btn-sm btn-outline-danger"
            @click="stopTerminal"
          >
            <i class="fas fa-stop mr-1"></i> Disconnect
          </button>
          <button
            v-if="terminalDone && !loginComplete"
            class="btn btn-sm btn-outline-secondary"
            @click="resetTerminal"
          >
            <i class="fas fa-redo mr-1"></i> Re-run
          </button>
          <button
            v-if="terminalDone && !loginComplete"
            class="btn btn-sm btn-success"
            @click="markComplete"
          >
            <i class="fas fa-check mr-1"></i> Login Complete — Continue
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
      height="320px"
      @clear="terminalOutput = []"
      @send-input="store.sendInteractiveInput($event)"
    />

    <!-- Error -->
    <div v-if="store.error" class="alert alert-danger mt-3 small py-2">
      <i class="fas fa-exclamation-triangle mr-1"></i>{{ store.error }}
    </div>

    <!-- Success state -->
    <div
      v-if="loginComplete"
      class="alert alert-success mt-3 d-flex align-items-center"
    >
      <i class="fas fa-check-circle fa-lg mr-3"></i>
      <div>
        <strong>GCS Login complete!</strong>
        <div class="small text-muted mt-1">
          The GCS Manager role database has been populated.
          <span v-if="hasServiceIdentity">
            Endpoint ownership has been transferred to the service account.
          </span>
          You can now create a storage gateway.
        </div>
        <button class="btn btn-success btn-sm mt-2" @click="$emit('next')">
          <i class="fas fa-arrow-right mr-1"></i> Continue to Storage Gateway
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onUnmounted } from 'vue';
import { useGlobusServiceStore } from '../../stores/globusServiceStore';
import CommandOutputPanel from './CommandOutputPanel.vue';
import api from '../../api';

const emit = defineEmits(['next', 'back']);
const store = useGlobusServiceStore();

const loading = ref(false);
const terminalActive = ref(false);
const terminalDone = ref(false);
const terminalOutput = ref([]);
const loginComplete = ref(false);

// True when GLOBUS_SERVICE_IDENTITY is configured (backend includes set-owner in cmd)
// We detect this by checking whether the returned command contains "set-owner"
const hasServiceIdentity = ref(false);

async function runLogin() {
  if (!store.currentService) return;
  loading.value = true;
  store.error = null;
  try {
    const res = await api.getGcsLoginCmd(store.currentService.id);
    const cmd = res.data.cmd;

    // Detect if set-owner is chained (service identity configured)
    hasServiceIdentity.value = cmd.includes('set-owner');

    // Open the interactive WebSocket terminal in the node container
    terminalOutput.value = [];
    terminalActive.value = true;
    terminalDone.value = false;
    loginComplete.value = false;

    const ws = store.connectInteractive(store.currentService.id);

    // Route all store output to our local terminal output array
    const origAppend = store.appendOutput.bind(store);
    store.appendOutput = (type, text) => {
      terminalOutput.value.push({ type, text, timestamp: new Date().toISOString() });
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
          terminalActive.value = false;
          terminalDone.value = true;
          store.appendOutput = origAppend;
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
    store.error = err.response?.data?.error || 'Failed to get GCS login command.';
  } finally {
    loading.value = false;
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
  loginComplete.value = false;
  store.error = null;
}

function markComplete() {
  loginComplete.value = true;
}

onUnmounted(() => {
  if (terminalActive.value) store.disconnectInteractive();
});
</script>
