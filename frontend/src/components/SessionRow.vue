<template>
  <tr @click="expanded = !expanded" class="accordion-toggle" :class="rowClass" style="cursor: pointer">
    <td>
      <span class="fa-solid" :class="expanded ? 'fa-chevron-down' : 'fa-chevron-right'"></span>
    </td>
    <td> {{ session.id }} </td>
    <td> {{ session.user }} </td>
    <td>
      <div v-for="n in session.nodes" :key="n">
        <i>{{ n }}</i>
      </div>
    </td>
    <td> {{ session.image }} </td>
    <td> {{ session.profile }} </td>
    <td>
      <span class="badge" :class="stateClass">{{ session.state }}</span>
    </td>
    <td>
      <div class="btn-group" @click.stop>
        <button v-if="canStart" title="start" @click="store.startSession(session.id)" class="btn btn-sm btn-success">
          <i class="fa-solid fa-play"></i>
        </button>
        <button v-if="canStop" title="stop" @click="store.stopSession(session.id)" class="btn btn-sm btn-secondary">
          <i class="fa-solid fa-stop"></i>
        </button>
        <button v-if="canDelete" title="delete" @click="store.deleteSession(session.id)" class="btn btn-sm btn-danger">
          <i class="fa-solid fa-xmark"></i>
        </button>
      </div>
    </td>
  </tr>
  <tr v-if="expanded">
    <td colspan="8" class="p-0 border-top-0">
      <div class="p-3 bg-white border-bottom shadow-sm">
        
        <!-- Action Toolbar for expanded view -->
        <div class="d-flex justify-content-end mb-3 border-bottom pb-2">
            <div class="btn-group btn-group-sm">
                <button class="btn" :class="showPerf ? 'btn-primary' : 'btn-outline-primary'" 
                    v-if="session.tools && session.tools.length" @click="showPerf = !showPerf">
                    <i class="fas fa-bolt mr-1"></i> {{ showPerf ? 'Hide' : 'Show' }} Perf Test
                </button>
                <button class="btn" :class="showLogs ? 'btn-info' : 'btn-outline-info'" @click="showLogs = !showLogs">
                    <i class="fas fa-terminal mr-1"></i> {{ showLogs ? 'Hide' : 'Show' }} Logs
                </button>
            </div>
        </div>

        <!-- Row 1: Service Details -->
        <div class="row mb-4">
          <div class="col-12">
            <h5 class="small font-weight-bold text-uppercase text-muted mb-3"><i class="fas fa-info-circle mr-2"></i>Service Details</h5>
            <table class="table table-sm table-bordered mb-0" style="font-size: 0.9rem;">
              <thead>
                <tr class="bg-light text-secondary">
                  <th>Endpoint</th>
                  <th>SSH Connection</th>
                  <th>Control Port</th>
                  <th>Service Port</th>
                  <th>Data Interfaces</th>
                </tr>
              </thead>
              <tbody>
                <template v-for="(srvs, nodeName) in session.data.services" :key="nodeName">
                  <tr v-for="srv in srvs" :key="srv.container_id">
                    <td><b>{{ nodeName }}</b></td>
                    <td><code>ssh {{ srv.container_user || 'user' }}@{{ srv.ctrl_host }} -p {{ srv.ctrl_port }}</code></td>
                    <td>{{ srv.ctrl_port }}</td>
                    <td>{{ srv.serv_port }}</td>
                    <td>{{ srv.data_ipv4 }}{{ srv.data_ipv6 ? ', ' + srv.data_ipv6 : '' }}</td>
                  </tr>
                </template>
              </tbody>
            </table>
          </div>
        </div>
        
        <!-- Row 2: Performance Test -->
        <div class="row mb-4" v-if="showPerf && session.tools && session.tools.length">
          <div class="col-12">
            <div class="d-flex justify-content-between align-items-center border-bottom pb-2 mb-3">
                <h5 class="text-primary mb-0"><i class="fas fa-bolt mr-2"></i>Performance Test</h5>
                <button class="close" @click="showPerf = false">&times;</button>
            </div>
            <div class="card border-0 bg-light p-3">
              <div class="row align-items-center">
                <div class="col-md-3">
                  <label class="small font-weight-bold text-uppercase text-muted mb-1">Select Tool</label>
                  <select v-model="perfTool" class="custom-select custom-select-sm" :disabled="perfRunning">
                    <option value="" disabled>Select tool...</option>
                    <option v-for="tool in session.tools" :key="tool" :value="tool">{{ tool }}</option>
                  </select>
                </div>
                <div class="col-md-4">
                  <label class="small font-weight-bold text-uppercase text-muted mb-1">Destination Override</label>
                  <input v-model="perfHost" type="text" class="form-control form-control-sm" placeholder="e.g. 10.0.0.1" :disabled="perfRunning">
                </div>
                <div class="col-md-2">
                  <label class="small font-weight-bold text-uppercase text-muted mb-1">Duration</label>
                  <input v-model="perfDuration" type="number" class="form-control form-control-sm" placeholder="sec" :disabled="perfRunning">
                </div>
                <div class="col-md-3 text-right mt-4 mt-md-0">
                  <button class="btn btn-success btn-sm px-4" type="button" @click="runPerfTest" :disabled="session.state !== 'STARTED' || perfRunning || !perfTool">
                    <i class="fas" :class="perfRunning ? 'fa-spinner fa-spin' : 'fa-play-circle mr-1'"></i>
                    {{ perfRunning ? 'Running...' : 'Start Test' }}
                  </button>
                </div>
              </div>
              <div v-if="perfOutput" class="mt-3">
                <textarea id="perf-output" readonly class="form-control form-control-sm" 
                  style="font-family: 'Courier New', Courier, monospace; height: 250px; background-color: #1e1e1e; color: #76ea64; border: 1px solid #333;" 
                  v-model="perfOutput"></textarea>
              </div>
            </div>
          </div>
        </div>
        
        <!-- Row 3: Container Logs -->
        <div class="row" v-if="showLogs">
          <div class="col-12">
            <div class="d-flex justify-content-between align-items-center border-bottom pb-2 mb-3">
                <h5 class="text-info mb-0"><i class="fas fa-terminal mr-2"></i>Container Logs</h5>
                <button class="close" @click="showLogs = false">&times;</button>
            </div>
            <div class="card border-0 bg-light p-3">
              <div class="row align-items-center mb-3">
                <div class="col-md-4">
                  <label class="small font-weight-bold text-uppercase text-muted mb-1">Target Node</label>
                  <select v-model="logNode" class="custom-select custom-select-sm">
                    <option value="" disabled>Select node...</option>
                    <option v-for="n in session.nodes" :key="n" :value="n">{{ n }}</option>
                  </select>
                </div>
                <div class="col-md-4">
                  <div class="custom-control custom-checkbox mt-4">
                    <input type="checkbox" class="custom-control-input" v-model="logTimestamps" :id="'ts-check-' + session.id">
                    <label class="custom-control-label small font-weight-bold text-uppercase text-muted" :for="'ts-check-' + session.id">Include Timestamps</label>
                  </div>
                </div>
                <div class="col-md-4 text-right mt-4 mt-md-0">
                  <button class="btn btn-info btn-sm px-4" type="button" @click="fetchLogs" :disabled="!logNode">
                    <i class="fas fa-sync-alt mr-1"></i> Fetch Logs
                  </button>
                </div>
              </div>
              <textarea readonly class="form-control form-control-sm" 
                style="font-family: 'Courier New', Courier, monospace; height: 250px; background-color: #f8f9fa;" 
                v-model="logs"></textarea>
            </div>
          </div>
        </div>
      </div>
    </td>
  </tr>
</template>

<script setup>
import { ref, computed, onUnmounted, nextTick } from 'vue';
import { useSessionStore } from '../stores/sessionStore';
import api from '../api';

const props = defineProps(['session']);
const store = useSessionStore();
const expanded = ref(false);

// UI Toggle state
const showPerf = ref(false);
const showLogs = ref(false);

const canStart = computed(() => ['INITIALIZED', 'STOPPED'].includes(props.session.state));
const canStop = computed(() => ['STARTED', 'MIXED'].includes(props.session.state));
const canDelete = computed(() => props.session.state !== 'STARTED');

const stateClass = computed(() => {
  switch (props.session.state) {
    case 'STARTED': return 'badge-success';
    case 'STOPPED': return 'badge-secondary';
    case 'INITIALIZED': return 'badge-info';
    case 'MIXED': return 'badge-warning';
    case 'FAILED': return 'badge-danger';
    default: return 'badge-dark';
  }
});

const rowClass = computed(() => {
  if (perfRunning.value) return 'table-warning';
  return '';
});

// Perf test state
const perfTool = ref('');
const perfHost = ref('');
const perfDuration = ref(10);
const perfOutput = ref('');
const perfRunning = ref(false);
let perfSocket = null;

const runPerfTest = () => {
  if (!perfTool.value || perfRunning.value) return;

  perfRunning.value = true;
  perfOutput.value = `Starting performance test with ${perfTool.value}...\n`;

  const wsProtocol = window.location.protocol === 'https:' ? 'wss://' : 'ws://';
  const wsUrl = `${wsProtocol}${window.location.host}/ws/perf/`;
  
  perfSocket = new WebSocket(wsUrl);

  perfSocket.onopen = () => {
    const data = {
      'sess': props.session,
      'sid': props.session.id,
      'hostname': perfHost.value,
      'duration': perfDuration.value,
      'tool': perfTool.value
    };
    perfSocket.send(JSON.stringify(data));
  };

  perfSocket.onmessage = (e) => {
    const data = JSON.parse(e.data);
    if (data.data) {
      perfOutput.value += data.data.replace(/\0/g, '');
      // Auto-scroll logic
      nextTick(() => {
        const textarea = document.getElementById('perf-output');
        if (textarea) textarea.scrollTop = textarea.scrollHeight;
      });
    }
    if (data.done) {
      perfRunning.value = false;
      perfSocket.close();
    }
  };

  perfSocket.onerror = (err) => {
    perfOutput.value += "\n[Error]: WebSocket connection failed.";
    perfRunning.value = false;
  };

  perfSocket.onclose = () => {
    perfRunning.value = false;
    perfSocket = null;
  };
};

// Logs state
const logNode = ref(props.session.nodes[0] || '');
const logTimestamps = ref(false);
const logs = ref('');

const fetchLogs = async () => {
  if (!logNode.value) return;
  logs.value = "Fetching logs...";
  try {
    const response = await api.getLogs(props.session.id, logNode.value, logTimestamps.value);
    logs.value = response.data.response || '-- logs empty --';
  } catch (err) {
    logs.value = "Error fetching logs.";
  }
};

onUnmounted(() => {
  if (perfSocket) perfSocket.close();
});
</script>
