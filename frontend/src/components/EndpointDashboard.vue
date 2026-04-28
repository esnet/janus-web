<template>
  <div class="container-fluid" style="padding-top: 2%">
    <div v-if="store.error" class="alert alert-danger shadow-sm" role="alert">
      <i class="fas fa-exclamation-triangle mr-2"></i><b>{{ store.error }}</b>
    </div>

    <!-- Reactive Add Node Form -->
    <div v-if="addingNode" class="mb-4">
      <AddNodeForm @saved="handleSaved" @cancel="addingNode = false" />
    </div>

    <div v-if="!addingNode" class="card shadow-sm border-0">
      <div class="card-header bg-white d-flex justify-content-between align-items-center py-3">
        <h5 class="mb-0 text-muted text-uppercase small font-weight-bold">
            <span class="text-dark">Available</span> Endpoints
        </h5>
        <div class="d-flex align-items-center">
          <!-- Search Bar -->
          <div class="input-group input-group-sm mr-3" style="width: 250px">
            <div class="input-group-prepend">
              <span class="input-group-text bg-light border-right-0"><i class="fas fa-search text-muted"></i></span>
            </div>
            <input v-model="searchQuery" type="text" class="form-control border-left-0 bg-light" 
                   placeholder="Search by name..." aria-label="Search">
          </div>
          <button class="btn btn-sm btn-outline-secondary mr-2" @click="store.fetchNodes(true)" :disabled="store.loading">
            <i class="fas fa-sync" :class="{ 'fa-spin': store.loading }"></i> Refresh
          </button>
          <button class="btn btn-primary btn-sm" @click="addingNode = true">
            <i class="fas fa-plus mr-1"></i> Add Node
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
                <th class="border-top-0 py-3 text-center" style="width: 100px">Status</th>
                <th class="border-top-0 py-3" style="width: 200px">Name</th>
                <th class="border-top-0 py-3">URL</th>
                <th class="border-top-0 py-3" style="width: 150px">CPU Model</th>
                <th class="border-top-0 py-3 text-center" style="width: 80px">Cores</th>
                <th class="border-top-0 py-3 text-center" style="width: 100px">Memory</th>
                <th class="border-top-0 py-3 text-center" style="width: 80px">Images</th>
                <th class="border-top-0 py-3 text-center" style="width: 80px">Nets</th>
                <th class="border-top-0 text-right pr-4 py-3" style="width: 100px">Action</th>
              </tr>
            </thead>
            <tbody>
              <template v-for="node in paginatedNodes" :key="node.id">
                <EndpointRow :node="node" />
              </template>
              <tr v-if="filteredNodes.length === 0 && !store.loading">
                <td colspan="11" class="text-center p-5 text-muted">
                  <i class="fas fa-server fa-3x mb-3 d-block"></i>
                  No endpoints found<span v-if="searchQuery"> matching "{{ searchQuery }}"</span>.
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <PaginationControl 
            v-model:currentPage="currentPage" 
            :totalItems="filteredNodes.length" 
            :pageSize="pageSize" 
        />
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, computed, watch } from 'vue';
import { useEndpointStore } from '../stores/endpointStore';
import EndpointRow from './EndpointRow.vue';
import AddNodeForm from './AddNodeForm.vue';
import PaginationControl from './PaginationControl.vue';

const store = useEndpointStore();
const addingNode = ref(false);

const searchQuery = ref('');
const currentPage = ref(1);
const pageSize = 10;

const filteredNodes = computed(() => {
  if (!searchQuery.value) return store.nodes;
  const q = searchQuery.value.toLowerCase();
  return store.nodes.filter(n => n.name.toLowerCase().includes(q));
});

const paginatedNodes = computed(() => {
  const start = (currentPage.value - 1) * pageSize;
  return filteredNodes.value.slice(start, start + pageSize);
});

// Reset page when search query changes
watch(searchQuery, () => {
    currentPage.value = 1;
});

const handleSaved = () => {
  addingNode.value = false;
  store.fetchNodes();
};

onMounted(() => {
  store.fetchNodes();
});
</script>
