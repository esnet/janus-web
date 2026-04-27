<template>
  <tr @click="expanded = !expanded" class="accordion-toggle" style="cursor: pointer">
    <td>
      <span class="fa-solid" :class="expanded ? 'fa-chevron-down' : 'fa-chevron-right'"></span>
    </td>
    <td> {{ node.id }} </td>
    <td>
      <span :class="statusClass"><i class="fas fa-circle mr-1" style="font-size: 0.6rem"></i>{{ node.status || 'unknown' }}</span>
    </td>
    <td> 
      <div class="d-flex align-items-center">
        <img v-if="typeIcon" :src="typeIcon" width="20" class="mr-2" />
        <b>{{ node.name }}</b>
      </div>
    </td>
    <td> <code>{{ node.url }}</code> </td>
    <td> {{ node.cpu_model || 'N/A' }} </td>
    <td> {{ node.cpu_core || 0 }} </td>
    <td> {{ node.memory_str || 'N/A' }} </td>
    <td> {{ node.image || 0 }} </td>
    <td> {{ node.networks || 0 }} </td>
    <td>
      <div class="btn-group" @click.stop>
        <button title="remove" @click="store.removeNode(node.name)" class="btn btn-sm btn-danger">
          <i class="fa-solid fa-trash"></i>
        </button>
      </div>
    </td>
  </tr>
  <tr v-if="expanded">
    <td colspan="11" class="p-0 border-top-0">
      <div class="p-3 bg-white border-bottom shadow-sm">
        
        <!-- Action Toolbar -->
        <div class="d-flex justify-content-end mb-3 border-bottom pb-2" v-if="hasNetworks">
            <div class="btn-group btn-group-sm">
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
            <table class="table table-sm table-bordered small">
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
  return props.node.status === 'running' ? 'text-success' : 'text-danger';
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
