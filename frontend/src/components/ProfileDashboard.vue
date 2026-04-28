<template>
  <div class="container-fluid" style="padding-top: 2%">
    <div v-if="store.error" class="alert alert-danger shadow-sm" role="alert">
      <i class="fas fa-exclamation-triangle mr-2"></i><b>{{ store.error }}</b>
    </div>

    <!-- Tab Navigation -->
    <ul class="nav nav-pills mb-4 bg-white p-2 rounded shadow-sm" v-if="!editingProfile">
      <li class="nav-item">
        <a class="nav-link px-4" :class="{ active: activeTab === 'host' }" @click.prevent="activeTab = 'host'" href="#">
            <i class="fas fa-server mr-2"></i>Host
        </a>
      </li>
      <li class="nav-item">
        <a class="nav-link px-4" :class="{ active: activeTab === 'network' }" @click.prevent="activeTab = 'network'" href="#">
            <i class="fas fa-network-wired mr-2"></i>Network
        </a>
      </li>
      <li class="nav-item">
        <a class="nav-link px-4" :class="{ active: activeTab === 'volume' }" @click.prevent="activeTab = 'volume'" href="#">
            <i class="fas fa-hdd mr-2"></i>Volume
        </a>
      </li>
      <li class="nav-item">
        <a class="nav-link px-4" :class="{ active: activeTab === 'qos' }" @click.prevent="activeTab = 'qos'" href="#">
            <i class="fas fa-tachometer-alt mr-2"></i>QoS
        </a>
      </li>
    </ul>

    <div v-if="!editingProfile" class="card shadow-sm border-0">
      <div class="card-header bg-white d-flex justify-content-between align-items-center py-3">
        <h5 class="mb-0 text-muted text-uppercase small font-weight-bold">
            <span class="text-dark">{{ activeTab }}</span> Profiles
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
          <button class="btn btn-sm btn-outline-secondary mr-2" @click="store.fetchAll(true)" :disabled="store.loading">
            <i class="fas fa-sync" :class="{ 'fa-spin': store.loading }"></i> Refresh
          </button>
          <button class="btn btn-primary btn-sm" @click="startCreate">
            <i class="fas fa-plus mr-1"></i> Create
          </button>
        </div>
      </div>
      <div class="card-body p-0">
        <div class="table-responsive">
            <table class="table table-hover mb-0">
              <thead class="bg-light text-secondary small text-uppercase font-weight-bold">
                <tr>
                  <th class="border-top-0 pl-4 py-3" style="width: 220px">Profile Name</th>
                  <th class="border-top-0 py-3" style="width: 100px">Tags</th>
                  <th class="border-top-0 py-3">Configuration Summary</th>
                  <th class="border-top-0 text-right pr-4 py-3" style="width: 140px">Actions</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="profile in paginatedProfiles" :key="profile.name">
                  <td class="pl-4 align-middle">
                    <b>{{ profile.name }}</b>
                  </td>
                  <td class="align-middle">
                    <div class="d-flex align-items-center">
                        <i v-if="profile.is_system" class="fas fa-shield-halved text-primary mr-2" 
                           title="System Default (Locked)"></i>
                        <i v-if="profile.on_disk" class="fas fa-hard-drive text-secondary mr-2" 
                           title="Configuration-backed (from disk)"></i>
                        <i v-if="profile.is_modified" class="fas fa-pen-to-square text-warning" 
                           title="In-memory changes (not saved to disk)"></i>
                    </div>
                  </td>
                  <td class="align-middle">
                    <!-- Host Summary Grid -->
                    <div class="summary-grid host-grid text-muted small" v-if="activeTab === 'host'">
                        <div class="d-flex align-items-center">
                            <i class="fas fa-microchip mr-2 text-primary" style="width: 16px"></i> {{ profile.settings.cpu || '0' }} Cores
                        </div>
                        <div class="d-flex align-items-center">
                            <i class="fas fa-memory mr-2 text-info" style="width: 16px"></i> {{ formatMemory(profile.settings.memory) }}
                        </div>
                        <div class="d-flex flex-column justify-content-center text-truncate">
                            <div class="d-flex align-items-center mb-1" v-if="profile.settings.image">
                                <i class="fas fa-layer-group mr-2 text-secondary" style="width: 16px"></i> {{ profile.settings.image }}
                            </div>
                            <div class="d-flex align-items-center">
                                <i v-if="profile.settings.privileged" class="fas fa-user-shield mr-2 text-danger" title="Privileged"></i>
                                <i v-if="profile.settings.systemd" class="fas fa-cog mr-2 text-info" title="Systemd"></i>
                                <i v-if="profile.settings.pull_image" class="fas fa-download mr-2 text-success" title="Always Pull"></i>
                            </div>
                        </div>
                        <div class="d-flex flex-column justify-content-center">
                            <div class="d-flex align-items-center mb-1">
                                <i class="fas fa-network-wired mr-2 text-success" style="width: 16px"></i> 
                                <b>MGMT:</b> {{ getNetName(profile.settings.mgmt_net) }}
                                <span v-if="getNetIP(profile.settings.mgmt_net)" class="ml-1 text-info">({{ getNetIP(profile.settings.mgmt_net) }})</span>
                            </div>
                            <div class="d-flex align-items-center">
                                <i class="fas fa-network-wired mr-2 text-primary" style="width: 16px"></i> 
                                <b>DATA:</b> {{ getNetName(profile.settings.data_net) }}
                                <span v-if="getNetIP(profile.settings.data_net)" class="ml-1 text-info">({{ getNetIP(profile.settings.data_net) }})</span>
                            </div>
                        </div>
                    </div>
                    <!-- Network Summary Grid -->
                    <div class="summary-grid network-grid text-muted small" v-else-if="activeTab === 'network'">
                        <div class="d-flex align-items-center">
                            <i class="fas fa-id-card mr-2 text-primary" style="width: 16px"></i> <b>Driver:</b> {{ profile.settings.driver || 'default' }}
                        </div>
                        <div class="d-flex align-items-center">
                            <i class="fas fa-cog mr-2 text-info" style="width: 16px"></i> <b>Mode:</b> {{ profile.settings.mode || 'N/A' }}
                        </div>
                        <div class="d-flex align-items-center">
                            <i class="fas fa-globe mr-2" :class="profile.settings.enable_ipv6 ? 'text-success' : 'text-light'" style="width: 16px"></i>
                            IPv6 {{ profile.settings.enable_ipv6 ? 'Enabled' : 'Disabled' }}
                        </div>
                    </div>
                    <!-- Volume Summary Grid -->
                    <div class="summary-grid volume-grid text-muted small" v-else-if="activeTab === 'volume'">
                        <div class="d-flex align-items-center">
                            <i class="fas fa-tag mr-2 text-primary" style="width: 16px"></i> <b>Type:</b> {{ profile.settings.type || 'N/A' }}
                        </div>
                        <div class="d-flex align-items-center">
                            <i class="fas fa-exchange-alt mr-2 text-info" style="width: 16px"></i> {{ profile.settings.source }} <i class="fas fa-long-arrow-alt-right mx-1"></i> {{ profile.settings.target }}
                        </div>
                    </div>
                    <!-- QoS Summary Grid -->
                    <div class="summary-grid qos-grid text-muted small" v-else-if="activeTab === 'qos'">
                         <div class="d-flex align-items-center" v-for="(val, key) in profile.settings" :key="key" v-if="val">
                             <b class="text-uppercase mr-1">{{ key }}:</b> {{ val }}
                         </div>
                    </div>
                  </td>
                  <td class="text-right pr-4 align-middle">
                    <div class="btn-group btn-group-sm shadow-sm">
                      <button class="btn btn-white border" @click="startEdit(profile)" title="Edit">
                        <i class="fas fa-edit text-primary"></i>
                      </button>
                      <button class="btn btn-white border" @click="confirmDelete(profile.name)" :disabled="profile.is_system" title="Delete">
                        <i class="fas fa-trash text-danger"></i>
                      </button>
                    </div>
                  </td>
                </tr>
                <tr v-if="filteredProfiles.length === 0 && !store.loading">
                  <td colspan="4" class="text-center p-5 text-muted">
                    <i class="fas fa-inbox fa-3x mb-3 d-block"></i>
                    No profiles found<span v-if="searchQuery"> matching "{{ searchQuery }}"</span>.
                  </td>
                </tr>
              </tbody>
            </table>
        </div>
        <PaginationControl 
            v-model:currentPage="currentPage" 
            :totalItems="filteredProfiles.length" 
            :pageSize="pageSize" 
        />
      </div>
    </div>

    <!-- Reactive Profile Form -->
    <div v-if="editingProfile" class="card shadow-sm border-0 animated fadeIn">
        <div class="card-header bg-white py-3 border-bottom d-flex justify-content-between align-items-center">
            <h5 class="mb-0 font-weight-bold">
                <i class="fas fa-edit mr-2 text-primary"></i>
                {{ isNew ? 'Create' : 'Edit' }} {{ activeTab }} Profile: 
                <span class="text-muted">{{ editingProfile.name || 'New Profile' }}</span>
            </h5>
            <button class="btn btn-sm btn-light border" @click="cancelEdit">
                <i class="fas fa-times mr-1"></i> Cancel
            </button>
        </div>
        <div class="card-body p-4">
            <ProfileEditForm 
                :resource="activeTab" 
                :profile="editingProfile" 
                :is-new="isNew"
                @saved="handleSaved" 
                @cancel="cancelEdit" 
            />
        </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, computed, watch } from 'vue';
import { useProfileStore } from '../stores/profileStore';
import ProfileEditForm from './ProfileEditForm.vue';
import PaginationControl from './PaginationControl.vue';

const store = useProfileStore();
const activeTab = ref('host');
const editingProfile = ref(null);
const isNew = ref(false);

const searchQuery = ref('');
const currentPage = ref(1);
const pageSize = 10;

const currentProfiles = computed(() => {
  switch (activeTab.value) {
    case 'host': return store.profiles;
    case 'network': return store.networks;
    case 'volume': return store.volumes;
    case 'qos': return store.choices.qos.map(name => ({ name, settings: {}, is_system: true }));
    default: return [];
  }
});

const filteredProfiles = computed(() => {
  if (!searchQuery.value) return currentProfiles.value;
  const q = searchQuery.value.toLowerCase();
  return currentProfiles.value.filter(p => p.name.toLowerCase().includes(q));
});

const paginatedProfiles = computed(() => {
    const start = (currentPage.value - 1) * pageSize;
    return filteredProfiles.value.slice(start, start + pageSize);
});

// Reset page when tab or search query changes
watch([activeTab, searchQuery], () => {
    currentPage.value = 1;
});

const formatMemory = (bytes) => {
    if (!bytes) return 'default';
    if (typeof bytes === 'string') return bytes;
    const gb = bytes / (1024 * 1024 * 1024);
    return `${gb.toFixed(0)} GB`;
};

const getNetName = (net) => {
    if (!net) return 'none';
    if (typeof net === 'string') return net;
    return net.name || 'none';
};

const getNetIP = (net) => {
    if (!net || typeof net === 'string') return null;
    return net.ipv4_addr || net.ipv6_addr || null;
};

const startEdit = (profile) => {
    editingProfile.value = JSON.parse(JSON.stringify(profile));
    isNew.value = false;
};

const startCreate = () => {
    editingProfile.value = {
        name: '',
        settings: {}
    };
    isNew.value = true;
};

const cancelEdit = () => {
    editingProfile.value = null;
};

const handleSaved = () => {
    editingProfile.value = null;
    store.fetchAll();
};

const confirmDelete = (name) => {
    if (confirm(`Are you sure you want to delete the "${name}" profile?`)) {
        store.deleteProfile(activeTab.value, name);
    }
};

onMounted(() => {
  store.fetchAll();
});
</script>

<style scoped>
.summary-grid {
    display: grid;
    gap: 15px;
    align-items: center;
}
.host-grid {
    grid-template-columns: 100px 100px 200px 1fr;
}
.network-grid {
    grid-template-columns: 140px 140px 1fr;
}
.volume-grid {
    grid-template-columns: 120px 1fr;
}
.qos-grid {
    grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
}

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
.btn-white {
    background-color: white;
}
.btn-white:hover {
    background-color: #f8f9fa;
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
