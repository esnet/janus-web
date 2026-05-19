<template>
  <div class="container-fluid" style="padding-top: 2%">
    <div v-if="store.error" class="alert alert-danger shadow-sm" role="alert">
      <i class="fas fa-exclamation-triangle mr-2"></i><b>{{ store.error }}</b>
    </div>

    <div class="card shadow-sm border-0">
      <div class="card-header bg-white d-flex justify-content-between align-items-center py-3">
        <h5 class="mb-0 text-muted text-uppercase small font-weight-bold">
          <i class="fas fa-cogs mr-2 text-warning"></i>
          <span class="text-dark">Janus</span> Services
        </h5>
        <div class="d-flex align-items-center">
          <button
            class="btn btn-sm btn-outline-secondary mr-2"
            @click="store.fetchServices()"
            :disabled="store.loading"
          >
            <i class="fas fa-sync" :class="{ 'fa-spin': store.loading }"></i> Refresh
          </button>
          <!-- Create New Service dropdown -->
          <div class="dropdown">
            <button
              class="btn btn-primary btn-sm dropdown-toggle"
              type="button"
              id="createServiceDropdown"
              data-toggle="dropdown"
              aria-haspopup="true"
              aria-expanded="false"
            >
              <i class="fas fa-plus mr-1"></i> Create New Service
            </button>
            <div class="dropdown-menu dropdown-menu-right shadow-sm border-0" aria-labelledby="createServiceDropdown">
              <h6 class="dropdown-header text-uppercase small font-weight-bold text-muted">Service Type</h6>
              <a class="dropdown-item d-flex align-items-center" href="/janus/services/globus/">
                <i class="fas fa-globe mr-2 text-primary"></i>
                Globus Connect Server
              </a>
            </div>
          </div>
        </div>
      </div>

      <div class="card-body p-0">
        <!-- Loading state -->
        <div v-if="store.loading && store.services.length === 0" class="text-center py-5 text-muted">
          <i class="fas fa-spinner fa-spin fa-2x mb-3 d-block"></i>
          Loading services...
        </div>

        <!-- Empty state -->
        <div v-else-if="store.services.length === 0" class="text-center py-5 text-muted">
          <i class="fas fa-cogs fa-3x mb-3 d-block"></i>
          No services configured yet.
          <div class="mt-2">
            <a href="/janus/services/globus/" class="btn btn-primary btn-sm">
              <i class="fas fa-plus mr-1"></i> Create a Globus Service
            </a>
          </div>
        </div>

        <!-- Services table -->
        <div v-else class="table-responsive">
          <table class="table table-hover mb-0">
            <thead class="bg-light text-secondary small text-uppercase font-weight-bold">
              <tr>
                <th class="border-top-0 pl-4 py-3" style="width: 60px">ID</th>
                <th class="border-top-0 py-3">Display Name</th>
                <th class="border-top-0 py-3">Type</th>
                <th class="border-top-0 py-3">Session</th>
                <th class="border-top-0 py-3">Endpoint ID</th>
                <th class="border-top-0 py-3 text-center" style="width: 160px">Status</th>
                <th class="border-top-0 py-3">Created</th>
                <th class="border-top-0 text-right pr-4 py-3" style="width: 160px">Actions</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="service in store.services" :key="service.id">
                <td class="pl-4 align-middle text-muted small">{{ service.id }}</td>
                <td class="align-middle">
                  <strong>{{ service.display_name || '(unnamed)' }}</strong>
                </td>
                <td class="align-middle">
                  <span class="badge badge-light border">
                    <i class="fas fa-globe mr-1 text-primary"></i> Globus
                  </span>
                </td>
                <td class="align-middle text-muted small">
                  Session #{{ service.session_id }}
                  <div class="text-muted" style="font-size: 0.75rem;">{{ service.node_name }}</div>
                </td>
                <td class="align-middle">
                  <code v-if="service.globus_endpoint_id" class="small">
                    {{ service.globus_endpoint_id }}
                  </code>
                  <span v-else class="text-muted small">—</span>
                </td>
                <td class="align-middle text-center">
                  <span class="badge" :class="statusBadgeClass(service.status)">
                    {{ statusLabel(service.status) }}
                  </span>
                </td>
                <td class="align-middle text-muted small">
                  {{ formatDate(service.created_at) }}
                </td>
                <td class="align-middle text-right pr-4">
                  <a
                    :href="`/janus/services/globus/?resume=${service.id}`"
                    class="btn btn-sm btn-outline-primary mr-1"
                    title="Resume configuration"
                  >
                    <i class="fas fa-play"></i>
                  </a>
                  <button
                    class="btn btn-sm btn-outline-danger"
                    title="Delete service"
                    @click="confirmDelete(service)"
                    :disabled="store.loading"
                  >
                    <i class="fas fa-trash-alt"></i>
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <!-- Delete confirmation modal (simple inline approach) -->
    <div v-if="pendingDelete" class="modal-overlay" @click.self="pendingDelete = null">
      <div class="card shadow-lg border-0 p-4" style="max-width: 420px; margin: 10% auto;">
        <h5 class="font-weight-bold text-danger mb-3">
          <i class="fas fa-trash-alt mr-2"></i>Delete Service
        </h5>
        <p class="text-muted">
          Are you sure you want to delete
          <strong>{{ pendingDelete.display_name || `Service #${pendingDelete.id}` }}</strong>?
          This action cannot be undone.
        </p>
        <div class="d-flex justify-content-end mt-3">
          <button class="btn btn-outline-secondary mr-2" @click="pendingDelete = null">Cancel</button>
          <button class="btn btn-danger" @click="doDelete" :disabled="store.loading">
            <i class="fas fa-trash-alt mr-1"></i> Delete
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue';
import { useGlobusServiceStore } from '../../stores/globusServiceStore';

const store = useGlobusServiceStore();
const pendingDelete = ref(null);

onMounted(() => {
  store.fetchServices();
});

function statusBadgeClass(status) {
  const map = {
    pending: 'badge-secondary',
    auth_complete: 'badge-info',
    endpoint_configured: 'badge-primary',
    node_configured: 'badge-primary',
    gateway_configured: 'badge-warning',
    collections_configured: 'badge-success',
    complete: 'badge-success',
    error: 'badge-danger',
  };
  return map[status] || 'badge-secondary';
}

function statusLabel(status) {
  const map = {
    pending: 'Pending',
    auth_complete: 'Auth Done',
    endpoint_configured: 'Endpoint ✓',
    node_configured: 'Node ✓',
    gateway_configured: 'Gateway ✓',
    collections_configured: 'Collections ✓',
    complete: 'Complete',
    error: 'Error',
  };
  return map[status] || status;
}

function formatDate(isoStr) {
  if (!isoStr) return '—';
  try {
    return new Date(isoStr).toLocaleString();
  } catch {
    return isoStr;
  }
}

function confirmDelete(service) {
  pendingDelete.value = service;
}

async function doDelete() {
  if (!pendingDelete.value) return;
  await store.deleteService(pendingDelete.value.id);
  pendingDelete.value = null;
}
</script>

<style scoped>
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.4);
  z-index: 1050;
  display: flex;
  align-items: flex-start;
  justify-content: center;
}
</style>
