<template>
  <div class="container" style="padding-top: 2%">
    <div v-if="store.error" class="alert alert-danger" role="alert">
      <b>{{ store.error }}</b>
    </div>
    
    <div class="card bg-light mb-3">
      <div class="card-header d-flex justify-content-between align-items-center">
        <b>Active Sessions</b>
        <div>
          <button class="btn btn-sm btn-outline-secondary mr-2" @click="store.fetchSessions" :disabled="store.loading">
            <i class="fas fa-sync" :class="{ 'fa-spin': store.loading }"></i> Refresh
          </button>
          <a class="btn btn-primary btn-md" role="button" href="/janus/session/create/">Create</a>
        </div>
      </div>
      <div class="card-body p-0">
        <table class="table table-condensed table-striped mb-0">
          <thead>
            <tr>
              <th></th>
              <th>ID</th>
              <th>Created By</th>
              <th>Endpoints</th>
              <th>Container Image</th>
              <th>Container Profile</th>
              <th>State</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody>
            <template v-for="session in store.sessions" :key="session.id">
              <SessionRow :session="session" />
            </template>
            <tr v-if="store.sessions.length === 0 && !store.loading">
              <td colspan="8" class="text-center p-4">No active sessions found.</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<script setup>
import { onMounted, onUnmounted } from 'vue';
import { useSessionStore } from '../stores/sessionStore';
import SessionRow from './SessionRow.vue';

const store = useSessionStore();

let refreshInterval = null;

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
