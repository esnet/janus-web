<template>
  <tr @click="expanded = !expanded" class="accordion-toggle endpoint-row" :class="{ 'is-expanded': expanded }" style="cursor: pointer">
    <td class="align-middle pl-4">
      <span class="fa-solid" :class="expanded ? 'fa-chevron-down' : 'fa-chevron-right'"></span>
    </td>
    <td class="align-middle"> {{ node.id }} </td>
    <td class="align-middle">
      <div class="d-flex justify-content-center">
          <i class="fas fa-circle" :class="statusClass" :title="statusLabel" 
             style="font-size: 0.8rem; cursor: help;"></i>
      </div>
    </td>
    <td class="align-middle"> 
      <div class="d-flex align-items-center">
        <img v-if="typeIcon" :src="typeIcon" width="20" class="mr-2" />
        <b>{{ node.name }}</b>
      </div>
    </td>
    <td class="align-middle" style="max-width: 300px;"> 
      <div class="text-truncate" :title="node.url">
        <code>{{ node.url }}</code> 
      </div>
    </td>
    <td class="align-middle"> {{ node.cpu_model || 'N/A' }} </td>
    <td class="align-middle text-center"> {{ node.cpu_core || 0 }} </td>
    <td class="align-middle text-center"> {{ node.memory_str || 'N/A' }} </td>
    <td class="align-middle text-center"> {{ node.image || 0 }} </td>
    <td class="align-middle text-center"> {{ node.networks || 0 }} </td>
    <td class="align-middle pr-4 text-right">
      <div class="btn-group" @click.stop>
        <button title="remove" @click="store.removeNode(node.name)" class="btn btn-sm btn-danger">
          <i class="fa-solid fa-trash"></i>
        </button>
      </div>
    </td>
  </tr>
  <tr v-if="expanded" class="expanded-row">
    <td colspan="11" class="p-0 border-top-0">
      <div class="p-4 bg-white border-bottom shadow-sm mx-3 mb-3 rounded-bottom border-left border-right">
        
        <!-- Action Toolbar -->
        <div class="d-flex justify-content-end mb-4 border-bottom pb-3" v-if="hasNetworks">
            <div class="btn-group btn-group-sm shadow-sm">
                <button class="btn" :class="showNetworks ? 'btn-primary' : 'btn-outline-primary'" 
                    @click="showNetworks = !showNetworks">
                    <i class="fas fa-network-wired mr-1"></i> {{ showNetworks ? 'Hide' : 'Show' }} Networks
                </button>
            </div>
        </div>

        <div class="row">
          <!-- Docker Specific Details -->
          <div class="col-md-6" v-if="node.data.docker">
            <h5 class="small font-weight-bold text-uppercase text-muted mb-3"><i class="fas fa-info-circle mr-2"></i>System Info</h5>
            <ul class="list-unstyled small mb-0">
              <li><b>Architecture:</b> {{ node.data.docker.Architecture }}</li>
              <li><b>OS:</b> {{ node.data.docker.OperatingSystem }} ({{ node.data.docker.OSType }})</li>
              <li><b>Kernel:</b> {{ node.data.docker.KernelVersion }}</li>
              <li><b>Docker Version:</b> {{ node.data.docker.ServerVersion }}</li>
            </ul>
          </div>
          
          <!-- Kubernetes/Slurm Cluster Nodes -->
          <div class="col-md-12 mt-3" v-if="node.data.cluster_nodes && node.data.cluster_nodes.length">
            <h5 class="small font-weight-bold text-uppercase text-muted mb-3"><i class="fas fa-server mr-2"></i>Cluster Nodes</h5>
            <table class="table table-sm table-bordered small mb-0">
                <thead class="bg-light text-secondary">
                    <tr>
                        <th>Node Name</th>
                        <th>Addresses</th>
                    </tr>
                </thead>
                <tbody>
                    <tr v-for="cn in node.data.cluster_nodes" :key="cn.name">
                        <td>{{ cn.name }}</td>
                        <td>{{ cn.addresses.join(', ') }}</td>
                    </tr>
                </tbody>
            </table>
          </div>

          <!-- Networks -->
          <div class="col-md-12 mt-3" v-if="showNetworks && hasNetworks">
            <div class="d-flex justify-content-between align-items-center border-bottom pb-2 mb-3">
                <h5 class="small font-weight-bold text-uppercase text-primary mb-0"><i class="fas fa-network-wired mr-2"></i>Available Networks</h5>
                <button class="close" @click="showNetworks = false" style="font-size: 1.2rem">&times;</button>
            </div>
            <table class="table table-sm table-bordered small mb-0">
                <thead class="bg-light text-secondary">
                    <tr>
                        <th>Network</th>
                        <th>Driver</th>
                        <th>Parent</th>
                        <th>Subnets</th>
                    </tr>
                </thead>
                <tbody>
                    <tr v-for="(net, name) in node.data.networks" :key="name">
                        <td><b>{{ name }}</b></td>
                        <td>{{ net.driver }}</td>
                        <td>{{ net.parent || '-' }}</td>
                        <td>
                            <div v-for="s in net.subnet" :key="s.Subnet">
                                {{ s.Subnet }}
                            </div>
                        </td>
                    </tr>
                </tbody>
            </table>
          </div>
        </div>
      </div>
    </td>
  </tr>
</template>

<script setup>
import { ref, computed } from 'vue';
import { useEndpointStore } from '../stores/endpointStore';

const props = defineProps(['node']);
const store = useEndpointStore();
const expanded = ref(false);
const showNetworks = ref(false);

const hasNetworks = computed(() => {
    return props.node.data.networks && Object.keys(props.node.data.networks).length > 0;
});

const statusClass = computed(() => {
  if (props.node.status === 1 || props.node.status === 'running') return 'text-success';
  if (props.node.status === 2 || props.node.status === 'down') return 'text-danger';
  return 'text-muted';
});

const statusLabel = computed(() => {
  if (props.node.status === 1 || props.node.status === 'running') return 'Online / Up';
  if (props.node.status === 2 || props.node.status === 'down') return 'Offline / Down';
  return 'Unknown / Unreachable';
});

const typeIcon = computed(() => {
  const type = props.node.data.backend_type;
  switch (type) {
    case 1: return '/static/img/docker.svg'; // Portainer
    case 2: return '/static/img/kube.png';   // Kube
    case 3: return '/static/img/docker.svg'; // Docker
    case 4: return '/static/img/slurm.svg';  // Slurm
    case 100: return '/static/img/janus_edge_transparent.png';
    default: return null;
  }
});
</script>

<style scoped>
.endpoint-row {
    transition: all 0.2s ease;
    border-left: 4px solid transparent;
}
.endpoint-row:hover {
    background-color: #f8f9fa;
}
.endpoint-row.is-expanded {
    background-color: #f1f8ff;
    border-left: 4px solid #28a745; /* Green for endpoints */
}
.endpoint-row td {
    border-top: 1px solid #dee2e6;
    border-bottom: 1px solid #dee2e6;
}
.expanded-row td {
    background-color: #f1f8ff;
    border-top: none !important;
}

/* Custom rounded inner container for expanded content */
.expanded-row > td > div {
    border-radius: 0 0 8px 8px;
    border: 1px solid #dee2e6;
    border-top: none;
}

.fa-chevron-right, .fa-chevron-down {
    width: 20px;
    text-align: center;
    color: #6c757d;
}

.is-expanded .fa-chevron-down {
    color: #28a745;
}

code {
    background-color: #f1f3f5;
    padding: 2px 4px;
    border-radius: 4px;
    color: #d63384;
}
</style>
