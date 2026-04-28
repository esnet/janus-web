<template>
  <div class="container-fluid" style="padding-top: 2%">
    <div v-if="store.error" class="alert alert-danger shadow-sm" role="alert">
      <i class="fas fa-exclamation-triangle mr-2"></i><b>{{ store.error }}</b>
    </div>

    <!-- Tab Navigation -->
    <ul class="nav nav-pills mb-4 bg-white p-2 rounded shadow-sm">
      <li class="nav-item">
        <a class="nav-link px-4" :class="{ active: activeTab === 'nodes' }" @click.prevent="activeTab = 'nodes'" href="#">
            <i class="fas fa-server mr-2"></i>Endpoints
        </a>
      </li>
      <li class="nav-item">
        <a class="nav-link px-4" :class="{ active: activeTab === 'profiles' }" @click.prevent="activeTab = 'profiles'" href="#">
            <i class="fas fa-id-card mr-2"></i>Profiles
        </a>
      </li>
      <li class="nav-item">
        <a class="nav-link px-4" :class="{ active: activeTab === 'images' }" @click.prevent="activeTab = 'images'" href="#">
            <i class="fas fa-box mr-2"></i>Containers
        </a>
      </li>
      <li class="nav-item">
        <a class="nav-link px-4" :class="{ active: activeTab === 'active' }" @click.prevent="activeTab = 'active'" href="#">
            <i class="fas fa-rocket mr-2"></i>Sessions
        </a>
      </li>
    </ul>

    <div class="card shadow-sm border-0 animated fadeIn">
      <div class="card-header bg-white d-flex justify-content-between align-items-center py-3">
        <div class="d-flex align-items-center">
            <h5 class="mb-0 text-muted text-uppercase small font-weight-bold mr-3">
                Manage Access: <span class="text-dark">{{ tabLabel }}</span>
            </h5>
            <button v-if="selectedIdentifiers.length > 1" 
                    class="btn btn-sm btn-primary shadow-sm animated fadeIn mr-3" 
                    @click="editBulkAccess">
                <i class="fas fa-users-cog mr-1"></i> Bulk Edit ({{ selectedIdentifiers.length }})
            </button>
            
            <!-- Search Bar -->
            <div class="input-group input-group-sm" style="width: 250px">
                <div class="input-group-prepend">
                <span class="input-group-text bg-light border-right-0"><i class="fas fa-search text-muted"></i></span>
                </div>
                <input v-model="searchQuery" type="text" class="form-control border-left-0 bg-light" 
                    placeholder="Search by name..." aria-label="Search">
            </div>
        </div>
        <button class="btn btn-sm btn-outline-secondary" @click="store.fetchAccessInfo" :disabled="store.loading">
          <i class="fas fa-sync" :class="{ 'fa-spin': store.loading }"></i> Refresh
        </button>
      </div>
      <div class="card-body p-0">
        <div class="table-responsive">
            <table class="table table-hover mb-0">
              <thead class="bg-light text-secondary small text-uppercase font-weight-bold">
                <tr>
                  <th class="border-top-0 pl-4 py-3" style="width: 50px">
                      <div class="custom-control custom-checkbox">
                          <input type="checkbox" class="custom-control-input" id="select-all" 
                                 :checked="isAllSelected" @change="toggleSelectAll">
                          <label class="custom-control-label" for="select-all"></label>
                      </div>
                  </th>
                  <th class="border-top-0 py-3" style="width: 25%">Resource Name</th>
                  <th class="border-top-0 py-3">Current Access (Users / Groups)</th>
                  <th class="border-top-0 text-right pr-4 py-3" style="width: 15%">Actions</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="item in paginatedItems" :key="item.id || item.name" 
                    :class="{ 'table-primary-light': isSelected(item) }">
                  <td class="pl-4 align-middle">
                      <div class="custom-control custom-checkbox">
                          <input type="checkbox" class="custom-control-input" :id="'select-' + (item.id || item.name)" 
                                 :value="item.id || item.name" v-model="selectedIdentifiers">
                          <label class="custom-control-label" :for="'select-' + (item.id || item.name)"></label>
                      </div>
                  </td>
                  <td class="align-middle">
                    <template v-if="activeTab !== 'active'">
                        <b>{{ item.name }}</b>
                    </template>
                    <template v-else>
                        <b>{{ item.name || 'Session #' + item.id }}</b>
                        <div class="small text-muted" v-if="item.name">#{{ item.id }} ({{ item.user }})</div>
                        <div class="small text-muted" v-else>({{ item.user }})</div>
                    </template>
                    <div class="small text-muted text-truncate" style="max-width: 200px" v-if="activeTab === 'nodes' && item.url">
                        {{ item.url }}
                    </div>
                  </td>
                  <td class="align-middle">
                    <div class="d-flex flex-wrap align-items-center">
                        <!-- Users -->
                        <span v-for="u in getAccess(item).users" :key="u" 
                              class="badge badge-primary mr-1 mb-1 shadow-sm">
                            <i class="fas fa-user mr-1 small"></i>{{ u }}
                        </span>
                        <!-- Groups -->
                        <span v-for="g in getAccess(item).groups" :key="g" 
                              class="badge badge-info mr-1 mb-1 shadow-sm">
                            <i class="fas fa-users mr-1 small"></i>{{ g }}
                        </span>
                        <span v-if="!getAccess(item).users.length && !getAccess(item).groups.length" 
                              class="text-muted small italic">No explicit access configured</span>
                    </div>
                  </td>
                  <td class="text-right pr-4 align-middle">
                    <button class="btn btn-sm btn-outline-primary shadow-sm" @click="editAccess(item)">
                        <i class="fas fa-user-lock mr-1"></i> Edit
                    </button>
                  </td>
                </tr>
                <tr v-if="filteredItems.length === 0 && !store.loading">
                  <td colspan="4" class="text-center p-5 text-muted">
                    <i class="fas fa-user-shield fa-3x mb-3 d-block"></i>
                    No resources found<span v-if="searchQuery"> matching "{{ searchQuery }}"</span>.
                  </td>
                </tr>
              </tbody>
            </table>
        </div>
        <PaginationControl 
            v-model:currentPage="currentPage" 
            :totalItems="filteredItems.length" 
            :pageSize="pageSize" 
        />
      </div>
    </div>

    <!-- Access Edit Modal Overlay -->
    <div v-if="editingItem || isBulkEditing" class="modal-backdrop animated fadeIn" @click.self="cancelEdit">
        <div class="modal-dialog modal-lg shadow-lg">
            <div class="modal-content border-0">
                <div class="modal-header bg-dark text-white">
                    <h5 class="modal-title font-weight-bold">
                        <i class="fas fa-user-shield mr-2"></i>
                        <template v-if="isBulkEditing">Bulk Edit Access ({{ selectedIdentifiers.length }} items)</template>
                        <template v-else>Edit Access: {{ editingItem.name || 'Session #' + editingItem.id }}</template>
                    </h5>
                    <button type="button" class="close text-white" @click="cancelEdit">&times;</button>
                </div>
                <div class="modal-body p-4">
                    <div class="row">
                        <div class="col-md-6">
                            <h6 class="small font-weight-bold text-uppercase text-muted mb-3">Authorize Users</h6>
                            <div class="user-group-list border rounded p-2 bg-light shadow-inner">
                                <div v-for="user in store.users" :key="user" class="custom-control custom-checkbox mb-1">
                                    <input type="checkbox" class="custom-control-input" :id="'user-' + user" 
                                           v-model="selectedUsers" :value="user">
                                    <label class="custom-control-label" :for="'user-' + user">{{ user }}</label>
                                </div>
                            </div>
                        </div>
                        <div class="col-md-6">
                            <h6 class="small font-weight-bold text-uppercase text-muted mb-3">Authorize Groups</h6>
                            <div class="user-group-list border rounded p-2 bg-light shadow-inner">
                                <div v-for="group in store.groups" :key="group" class="custom-control custom-checkbox mb-1">
                                    <input type="checkbox" class="custom-control-input" :id="'group-' + group" 
                                           v-model="selectedGroups" :value="group">
                                    <label class="custom-control-label" :for="'group-' + group">{{ group }}</label>
                                </div>
                            </div>
                        </div>
                    </div>
                    
                    <div class="mt-4 p-3 bg-light rounded border border-warning">
                         <div class="custom-control custom-switch">
                            <input type="checkbox" class="custom-control-input" id="remove-access-toggle" v-model="removeAccess">
                            <label class="custom-control-label font-weight-bold text-danger" for="remove-access-toggle">
                                REMOVE access for selected users/groups
                            </label>
                        </div>
                        <small class="text-muted d-block mt-1">
                            If enabled, selected users/groups will LOSE access. If disabled, they will GAIN access.
                            <b v-if="isBulkEditing" class="text-dark">This will apply to all {{ selectedIdentifiers.length }} selected resources.</b>
                        </small>
                    </div>
                </div>
                <div class="modal-footer bg-white border-top-0 pt-0 pb-4 pr-4">
                    <button class="btn btn-light border px-4" @click="cancelEdit">Cancel</button>
                    <button class="btn btn-primary px-5 shadow-sm" :disabled="saving" @click="saveAccess">
                        <i class="fas mr-2" :class="saving ? 'fa-spinner fa-spin' : 'fa-check-circle'"></i>
                        {{ saving ? 'Saving...' : 'Apply Access' }}
                    </button>
                </div>
            </div>
        </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, computed, watch } from 'vue';
import { useAuthStore } from '../stores/authStore';
import PaginationControl from './PaginationControl.vue';

const store = useAuthStore();
const activeTab = ref('nodes');
const editingItem = ref(null);
const isBulkEditing = ref(false);
const saving = ref(false);

const searchQuery = ref('');
const currentPage = ref(1);
const pageSize = 10;

const selectedIdentifiers = ref([]);
const selectedUsers = ref([]);
const selectedGroups = ref([]);
const removeAccess = ref(false);

const showRemoveToggle = ref(true); // Always show for now to match legacy behavior

const tabLabel = computed(() => {
    const labels = {
        'nodes': 'Endpoints',
        'profiles': 'Profiles',
        'images': 'Containers',
        'active': 'Active Sessions'
    };
    return labels[activeTab.value];
});

const currentItems = computed(() => {
    switch (activeTab.value) {
        case 'nodes': return store.nodes;
        case 'profiles': return store.profiles;
        case 'images': return store.images.map(img => ({ name: img.name, data: img }));
        case 'active': return store.sessions;
        default: return [];
    }
});

const filteredItems = computed(() => {
  if (!searchQuery.value) return currentItems.value;
  const q = searchQuery.value.toLowerCase();
  return currentItems.value.filter(item => {
    const name = item.name || `Session #${item.id} (${item.user})`;
    const idStr = item.id ? item.id.toString() : '';
    return name.toLowerCase().includes(q) || 
           idStr.includes(q) ||
           (item.url && item.url.toLowerCase().includes(q));
  });
});

const paginatedItems = computed(() => {
  const start = (currentPage.value - 1) * pageSize;
  return filteredItems.value.slice(start, start + pageSize);
});

const isAllSelected = computed(() => {
    return paginatedItems.value.length > 0 && 
           paginatedItems.value.every(item => selectedIdentifiers.value.includes(item.id || item.name));
});

const isSelected = (item) => {
    return selectedIdentifiers.value.includes(item.id || item.name);
};

const toggleSelectAll = (e) => {
    if (e.target.checked) {
        const pageIds = paginatedItems.value.map(item => item.id || item.name);
        selectedIdentifiers.value = [...new Set([...selectedIdentifiers.value, ...pageIds])];
    } else {
        const pageIds = paginatedItems.value.map(item => item.id || item.name);
        selectedIdentifiers.value = selectedIdentifiers.value.filter(id => !pageIds.includes(id));
    }
};

const getAccess = (item) => {
    let access = { users: [], groups: [] };
    
    if (activeTab.value === 'images') {
        access = item.data || access;
    } else if (activeTab.value === 'active') {
        access = item || access;
    } else {
        access = (item.data || item) || access;
    }

    return {
        users: access.users || [],
        groups: access.groups || []
    };
};

const editAccess = (item) => {
    isBulkEditing.value = false;
    editingItem.value = item;
    const access = getAccess(item);
    selectedUsers.value = [...(access.users || [])];
    selectedGroups.value = [...(access.groups || [])];
    removeAccess.value = false;
};

const editBulkAccess = () => {
    isBulkEditing.value = true;
    editingItem.value = null;
    selectedUsers.value = [];
    selectedGroups.value = [];
    removeAccess.value = false;
};

const cancelEdit = () => {
    editingItem.value = null;
    isBulkEditing.value = false;
};

const saveAccess = async () => {
    saving.value = true;
    
    let res;
    if (isBulkEditing.value) {
        res = await store.updateAccessBulk(
            activeTab.value,
            selectedIdentifiers.value,
            selectedUsers.value,
            selectedGroups.value,
            removeAccess.value
        );
    } else {
        const identifier = activeTab.value === 'active' ? editingItem.value.id : editingItem.value.name;
        res = await store.updateAccess(
            activeTab.value,
            identifier,
            selectedUsers.value,
            selectedGroups.value,
            removeAccess.value
        );
    }

    if (res.success) {
        editingItem.value = null;
        isBulkEditing.value = false;
        selectedIdentifiers.value = [];
    } else {
        alert(res.error);
    }
    saving.value = false;
};

// Clear selection and reset page when tab or search changes
watch([activeTab, searchQuery], () => {
    selectedIdentifiers.value = [];
    currentPage.value = 1;
});

onMounted(() => {
    // Read active tab from mount point if provided
    const el = document.getElementById('access-control-dashboard');
    if (el && el.dataset.tab) {
        activeTab.value = el.dataset.tab;
    }
    store.fetchAccessInfo();
});
</script>

<style scoped>
.nav-pills .nav-link {
    color: #6c757d;
    font-weight: 500;
    transition: all 0.2s ease;
    cursor: pointer;
}
.nav-pills .nav-link.active {
    background-color: #007bff;
    color: white;
    box-shadow: 0 4px 6px rgba(0, 123, 255, 0.2);
}
.nav-pills .nav-link:not(.active):hover {
    background-color: #f8f9fa;
    color: #007bff;
}

.table-primary-light {
    background-color: rgba(0, 123, 255, 0.05);
}

.modal-backdrop {
    position: fixed;
    top: 0;
    left: 0;
    width: 100vw;
    height: 100vh;
    background-color: rgba(0,0,0,0.5);
    display: flex;
    justify-content: center;
    align-items: center;
    z-index: 1050;
}

.user-group-list {
    max-height: 250px;
    overflow-y: auto;
}

.shadow-inner {
    box-shadow: inset 0 2px 4px rgba(0,0,0,0.06);
}

.animated {
    animation-duration: 0.3s;
    animation-fill-mode: both;
}
@keyframes fadeIn {
    from { opacity: 0; transform: translateY(10px); }
    to { opacity: 1; transform: translateY(0); }
}
.fadeIn {
    animation-name: fadeIn;
}
</style>
