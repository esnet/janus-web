<template>
  <div class="node-config-pane">
    <div class="card border-0 shadow-sm p-4 mb-3">
      <h5 class="font-weight-bold mb-1">
        <i class="fas fa-network-wired mr-2 text-success"></i>Node Setup
      </h5>
      <p class="text-muted small mb-2">
        Launch a new Janus session with the GCS image and your deployment key.
        The container will automatically run <code>globus-connect-server node setup</code>
        and start all GCS services (GCS Manager, Apache, GridFTP).
      </p>
      <div class="alert alert-info small py-2 mb-4">
        <i class="fas fa-info-circle mr-1"></i>
        This creates a <strong>new Janus session</strong> with <code>DEPLOYMENT_KEY</code>
        set from the key collected in the previous step. The wizard will update to point
        to the new node container automatically.
      </div>

      <form @submit.prevent="submit">
        <div class="form-row">
          <div class="form-group col-md-6">
            <label class="font-weight-bold small text-uppercase text-muted">
              Target Node
            </label>
            <input
              v-model="form.node_name"
              type="text"
              class="form-control"
              placeholder="e.g. benki"
              :disabled="store.loading"
            />
            <small class="form-text text-muted">
              Janus node to launch the GCS node container on.
              Defaults to the current session's node.
            </small>
          </div>
          <div class="form-group col-md-6">
            <label class="font-weight-bold small text-uppercase text-muted">
              NODE_SETUP_ARGS (optional)
            </label>
            <input
              v-model="form.node_setup_args"
              type="text"
              class="form-control"
              placeholder="Uses profile default if blank"
              :disabled="store.loading"
            />
            <small class="form-text text-muted">
              Override <code>NODE_SETUP_ARGS</code> env var (e.g.
              <code>--ip-address 192.168.1.81 --data-interface 192.168.1.81</code>).
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
              <i class="fas fa-spinner fa-spin mr-1"></i> Launching node container...
            </span>
            <span v-else>
              <i class="fas fa-rocket mr-1"></i> Launch Node Container
            </span>
          </button>
        </div>
      </form>
    </div>

    <!-- Output -->
    <CommandOutputPanel
      v-if="store.commandOutput.length > 0 || store.loading"
      :lines="store.commandOutput"
      :loading="store.loading"
      height="200px"
      @clear="store.clearOutput()"
    />

    <!-- Success -->
    <div
      v-if="store.currentService?.status === 'node_configured'"
      class="alert alert-success mt-3 d-flex align-items-center"
    >
      <i class="fas fa-check-circle fa-lg mr-3"></i>
      <div>
        <strong>Node container launched successfully!</strong>
        <div class="small text-muted mt-1">
          GCS Manager, Apache, and GridFTP are starting up.
          Wait ~15 seconds before proceeding to storage gateway creation.
        </div>
        <button class="btn btn-success btn-sm mt-2" @click="$emit('next')">
          <i class="fas fa-arrow-right mr-1"></i> Continue to Storage Gateway
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { reactive } from 'vue';
import { useGlobusServiceStore } from '../../stores/globusServiceStore';
import CommandOutputPanel from './CommandOutputPanel.vue';
import api from '../../api';

const emit = defineEmits(['next', 'back']);
const store = useGlobusServiceStore();

const form = reactive({
  node_name: store.currentService?.node_name || '',
  node_setup_args: '',
});

async function submit() {
  store.clearOutput();
  store.loading = true;
  store.error = null;
  try {
    const res = await api.setupGlobusNode(store.currentService.id, {
      node_name: form.node_name.trim(),
      node_setup_args: form.node_setup_args.trim(),
    });
    if (res.data.success) {
      store.currentService = res.data.service;
      store.appendOutput('info', `✓ Node container launched: ${res.data.container_id?.slice(0, 12) || ''}`);
      store.appendOutput('info', 'GCS services are starting. Please wait ~15 seconds before proceeding.');
    } else {
      const errMsg = res.data.error || 'Node launch failed';
      store.error = errMsg;
      store.appendOutput('error', errMsg);
    }
  } catch (err) {
    const msg = err.response?.data?.error || 'Node launch failed';
    store.error = msg;
    store.appendOutput('error', msg);
  } finally {
    store.loading = false;
  }
}
</script>
