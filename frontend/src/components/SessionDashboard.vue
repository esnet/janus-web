<template>
  <div class="container-fluid" style="padding-top: 2%">
    <div v-if="store.error" class="alert alert-danger shadow-sm" role="alert">
      <i class="fas fa-exclamation-triangle mr-2"></i><b>{{ store.error }}</b>
    </div>
    
    <!-- Reactive Create Session Form -->
    <div v-if="creatingSession" class="mb-4">
      <CreateSessionForm @saved="handleSaved" @cancel="creatingSession = false" />
    </div>

    <div v-if="!creatingSession" class="card shadow-sm border-0">
      <div class="card-header bg-white d-flex justify-content-between align-items-center py-3">
        <h5 class="mb-0 text-muted text-uppercase small font-weight-bold">
            <span class="text-dark">Active</span> Sessions
        </h5>
        <div class="d-flex align-items-center">
          <!-- Search Bar -->
          <div class="input-group input-group-sm mr-3" style="width: 250px">
            <div class="input-group-prepend">
              <span class="input-group-text bg-light border-right-0"><i class="fas fa-search text-muted"></i></span>
            </div>
            <input v-model="searchQuery" type="text" class="form-control border-left-0 bg-light" 
                   placeholder="Search by ID or user..." aria-label="Search">
          </div>
          <button class="btn btn-sm btn-outline-secondary mr-2" @click="store.fetchSessions" :disabled="store.loading">
            <i class="fas fa-sync" :class="{ 'fa-spin': store.loading }"></i> Refresh
          </button>
          <button class="btn btn-primary btn-sm" @click="creatingSession = true">
            <i class="fas fa-plus mr-1"></i> Create Session
          </button>
        </div>
      </div>
      <div class="card-body p-0">
        <div class="table-responsive">
          <table class="table table-hover mb-0">
            <thead class="bg-light text-secondary small text-uppercase font-weight-bold">
              <tr>
                <th class="border-top-0 pl-4 py-3" style="width: 40px"></th>
                <th class="border-top-0 py-3" style="width: 60px">ID</th>
                <th class="border-top-0 py-3" style="width: 200px">Name</th>
                <th class="border-top-0 py-3" style="width: 150px">Created By</th>
                <th class="border-top-0 py-3">Endpoints</th>
                <th class="border-top-0 py-3">Container Image</th>
                <th class="border-top-0 py-3" style="width: 180px">Container Profile</th>
                <th class="border-top-0 py-3 text-center" style="width: 120px">State</th>
                <th class="border-top-0 text-right pr-4 py-3" style="width: 120px">Action</th>
              </tr>
            </thead>
            <tbody>
              <template v-for="session in paginatedSessions" :key="session.id">
                <SessionRow :session="session" />
              </template>
              <tr v-if="filteredSessions.length === 0 && !store.loading">
                <td colspan="9" class="text-center p-5 text-muted">
                  <i class="fas fa-rocket fa-3x mb-3 d-block"></i>
                  No sessions found<span v-if="searchQuery"> matching "{{ searchQuery }}"</span>.
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <PaginationControl 
            v-model:currentPage="currentPage" 
            :totalItems="filteredSessions.length" 
            :pageSize="pageSize" 
        />
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, computed, watch } from 'vue';
import { useSessionStore } from '../stores/sessionStore';
import SessionRow from './SessionRow.vue';
import CreateSessionForm from './CreateSessionForm.vue';
import PaginationControl from './PaginationControl.vue';

const store = useSessionStore();
const creatingSession = ref(false);

const searchQuery = ref('');
const currentPage = ref(1);
const pageSize = 10;

const filteredSessions = computed(() => {
  if (!searchQuery.value) return store.sessions;
  const q = searchQuery.value.toLowerCase();
  return store.sessions.filter(s => 
    s.id.toString().includes(q) || 
    (s.name && s.name.toLowerCase().includes(q)) ||
    s.user.toLowerCase().includes(q) ||
    s.image.toLowerCase().includes(q)
  );
});

const paginatedSessions = computed(() => {
  const start = (currentPage.value - 1) * pageSize;
  return filteredSessions.value.slice(start, start + pageSize);
});

// Reset page when search query changes
watch(searchQuery, () => {
    currentPage.value = 1;
});

let refreshInterval = null;

const handleSaved = () => {
  creatingSession.value = false;
  store.fetchSessions();
};

onMounted(() => {
  store.fetchSessions();
  store.initWebSocket();
  // Poll for updates every 60 seconds as a final fallback
  refreshInterval = setInterval(() => {
    store.fetchSessions();
  }, 60000);
});

onUnmounted(() => {
  if (refreshInterval) clearInterval(refreshInterval);
});
</script>
