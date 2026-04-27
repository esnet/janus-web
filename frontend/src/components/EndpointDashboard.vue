<template>
  <div class="container" style="padding-top: 2%">
    <div v-if="store.error" class="alert alert-danger" role="alert">
      <b>{{ store.error }}</b>
    </div>

    <div class="card bg-light mb-3">
      <div class="card-header d-flex justify-content-between align-items-center">
        <b>Endpoints</b>
        <div>
          <button class="btn btn-sm btn-outline-secondary mr-2" @click="store.fetchNodes(true)" :disabled="store.loading">
            <i class="fas fa-sync" :class="{ 'fa-spin': store.loading }"></i> Refresh
          </button>
          <a class="btn btn-primary btn-md" role="button" href="/janus/nodes/add/">Add Node</a>
        </div>
      </div>
      <div class="card-body p-0">
        <table class="table table-condensed table-striped mb-0">
          <thead>
            <tr>
              <th></th>
              <th>ID</th>
              <th>Status</th>
              <th>Name</th>
              <th>URL</th>
              <th>CPU Model</th>
              <th>Cores</th>
              <th>Memory</th>
              <th>Images</th>
              <th>Networks</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody>
            <template v-for="node in store.nodes" :key="node.id">
              <EndpointRow :node="node" />
            </template>
            <tr v-if="store.nodes.length === 0 && !store.loading">
              <td colspan="11" class="text-center p-4">No endpoints found.</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<script setup>
import { onMounted } from 'vue';
import { useEndpointStore } from '../stores/endpointStore';
import EndpointRow from './EndpointRow.vue';

const store = useEndpointStore();

onMounted(() => {
  store.fetchNodes();
});
</script>
