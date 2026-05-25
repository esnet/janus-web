import { defineStore } from 'pinia';
import api from '../api';

// Helper: ensure text sent to container stdin ends with newline
function withNewline(text) {
  return text.endsWith('\n') ? text : text + '\n';
}

export const useGlobusServiceStore = defineStore('globusService', {
  state: () => ({
    services: [],
    currentService: null,
    currentStep: 0,       // 0=select session, 1=auth, 2=endpoint, 3=node, 4=gateway, 5=collections
    isAuthenticated: false,
    loading: false,
    error: null,
    commandOutput: [],    // Array of {type: 'stdout'|'stderr'|'info'|'error', text: string}
    interactiveWs: null,  // Active WebSocket for interactive sessions
  }),

  getters: {
    hasActiveService: (state) => state.currentService !== null,
    currentServiceId: (state) => state.currentService?.id ?? null,
    canProceedToStep: (state) => (step) => {
      switch (step) {
        case 1: return !!state.currentService;
        case 2: return state.isAuthenticated;
        case 3: return state.currentService?.status === 'endpoint_configured';
        case 4: return state.currentService?.status === 'node_configured';
        case 5: return state.currentService?.status === 'gateway_configured';
        default: return true;
      }
    },
  },

  actions: {
    // -----------------------------------------------------------------------
    // Output log helpers
    // -----------------------------------------------------------------------
    appendOutput(type, text) {
      this.commandOutput.push({ type, text, timestamp: new Date().toISOString() });
    },
    clearOutput() {
      this.commandOutput = [];
    },

    // -----------------------------------------------------------------------
    // Service list / CRUD
    // -----------------------------------------------------------------------
    async fetchServices() {
      this.loading = true;
      try {
        const res = await api.getGlobusServices();
        this.services = res.data.services;
        this.error = null;
      } catch (err) {
        this.error = err.response?.data?.error || 'Failed to fetch services';
      } finally {
        this.loading = false;
      }
    },

    async createService(sessionId, nodeName, containerId, displayName = '') {
      this.loading = true;
      try {
        const res = await api.createGlobusService({
          session_id: sessionId,
          node_name: nodeName,
          container_id: containerId,
          display_name: displayName,
        });
        this.currentService = res.data.service;
        this.services.push(this.currentService);
        this.error = null;
        return { success: true, service: this.currentService };
      } catch (err) {
        this.error = err.response?.data?.error || 'Failed to create service';
        return { success: false, error: this.error };
      } finally {
        this.loading = false;
      }
    },

    async loadService(serviceId) {
      this.loading = true;
      try {
        const res = await api.getGlobusService(serviceId);
        this.currentService = res.data.service;
        // Restore wizard step from service status
        this.currentStep = this._stepFromStatus(this.currentService.status);
        this.error = null;
      } catch (err) {
        this.error = err.response?.data?.error || 'Failed to load service';
      } finally {
        this.loading = false;
      }
    },

    async deleteService(serviceId) {
      this.loading = true;
      try {
        await api.deleteGlobusService(serviceId);
        this.services = this.services.filter(s => s.id !== serviceId);
        if (this.currentService?.id === serviceId) {
          this.currentService = null;
          this.currentStep = 0;
        }
        this.error = null;
        return { success: true };
      } catch (err) {
        this.error = err.response?.data?.error || 'Failed to delete service';
        return { success: false, error: this.error };
      } finally {
        this.loading = false;
      }
    },

    // -----------------------------------------------------------------------
    // Globus Auth
    // -----------------------------------------------------------------------
    async checkAuthStatus() {
      try {
        const res = await api.getGlobusAuthStatus();
        this.isAuthenticated = res.data.authenticated;
      } catch (err) {
        this.isAuthenticated = false;
      }
    },

    async getAuthUrl() {
      try {
        const res = await api.getGlobusAuthUrl();
        return { success: true, authUrl: res.data.auth_url, state: res.data.state };
      } catch (err) {
        this.error = err.response?.data?.error || 'Failed to get auth URL';
        return { success: false, error: this.error };
      }
    },

    async exchangeCode(code, state) {
      this.loading = true;
      try {
        await api.exchangeGlobusCode({ code, state });
        this.isAuthenticated = true;
        this.error = null;
        return { success: true };
      } catch (err) {
        this.error = err.response?.data?.error || 'Authentication failed';
        return { success: false, error: this.error };
      } finally {
        this.loading = false;
      }
    },

    async globusLogout() {
      try {
        await api.globusAuthLogout();
        this.isAuthenticated = false;
      } catch (err) {
        console.error('Globus logout error:', err);
      }
    },

    // -----------------------------------------------------------------------
    // GCS wizard steps
    // -----------------------------------------------------------------------
    async setupEndpoint(config) {
      if (!this.currentService) return { success: false, error: 'No active service' };
      this.loading = true;
      this.clearOutput();
      try {
        const res = await api.setupGlobusEndpoint(this.currentService.id, config);
        this.appendOutput('stdout', res.data.output || '');
        this.currentService = res.data.service;
        if (res.data.success) {
          this.currentStep = 3;
        }
        return { success: res.data.success, output: res.data.output };
      } catch (err) {
        const msg = err.response?.data?.error || 'Endpoint setup failed';
        this.appendOutput('error', msg);
        return { success: false, error: msg };
      } finally {
        this.loading = false;
      }
    },

    async setupNode(config) {
      if (!this.currentService) return { success: false, error: 'No active service' };
      this.loading = true;
      this.clearOutput();
      try {
        const res = await api.setupGlobusNode(this.currentService.id, config);
        this.appendOutput('stdout', res.data.output || '');
        this.currentService = res.data.service;
        if (res.data.success) {
          this.currentStep = 4;
        }
        return { success: res.data.success, output: res.data.output };
      } catch (err) {
        const msg = err.response?.data?.error || 'Node setup failed';
        this.appendOutput('error', msg);
        return { success: false, error: msg };
      } finally {
        this.loading = false;
      }
    },

    async createGateway(config) {
      if (!this.currentService) return { success: false, error: 'No active service' };
      this.loading = true;
      this.error = null;
      try {
        const res = await api.createGlobusGateway(this.currentService.id, config);
        this.currentService = res.data.service;
        if (res.data.success) {
          this.currentStep = 5;
          this.appendOutput('info', `Gateway created: ${res.data.gateway_id}`);
        } else {
          const msg = res.data.error || 'Storage gateway creation failed';
          this.error = msg;
          this.appendOutput('error', msg);
        }
        return { success: res.data.success, gateway_id: res.data.gateway_id };
      } catch (err) {
        const msg = err.response?.data?.error || 'Storage gateway creation failed';
        this.error = msg;
        this.appendOutput('error', msg);
        return { success: false, error: msg };
      } finally {
        this.loading = false;
      }
    },

    async createCollection(config) {
      if (!this.currentService) return { success: false, error: 'No active service' };
      this.loading = true;
      this.error = null;
      try {
        const res = await api.createGlobusCollection(this.currentService.id, config);
        this.currentService = res.data.service;
        if (res.data.success) {
          this.appendOutput('info', `Collection created: ${res.data.collection_id}`);
        } else {
          const msg = res.data.error || 'Collection creation failed';
          this.error = msg;
          this.appendOutput('error', msg);
        }
        return { success: res.data.success, collection_id: res.data.collection_id };
      } catch (err) {
        const msg = err.response?.data?.error || 'Collection creation failed';
        this.error = msg;
        this.appendOutput('error', msg);
        return { success: false, error: msg };
      } finally {
        this.loading = false;
      }
    },

    async execCommand(cmd) {
      if (!this.currentService) return { success: false, error: 'No active service' };
      this.loading = true;
      try {
        const res = await api.execGlobusCommand(this.currentService.id, cmd);
        this.appendOutput('stdout', res.data.output || '');
        return { success: res.data.success, output: res.data.output };
      } catch (err) {
        const msg = err.response?.data?.error || 'Command execution failed';
        this.appendOutput('error', msg);
        return { success: false, error: msg };
      } finally {
        this.loading = false;
      }
    },

    // -----------------------------------------------------------------------
    // Interactive WebSocket session
    // -----------------------------------------------------------------------
    connectInteractive(serviceId) {
      if (this.interactiveWs) {
        this.interactiveWs.close();
        this.interactiveWs = null;
      }

      const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
      const wsUrl = `${protocol}://${window.location.host}/ws/gcs-interactive/${serviceId}/`;

      const ws = new WebSocket(wsUrl);

      ws.onopen = () => {
        this.appendOutput('info', 'Interactive session connected.');
      };

      ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data);
          if (msg.type === 'stdout') {
            this.appendOutput('stdout', msg.data);
          } else if (msg.type === 'error') {
            this.appendOutput('error', msg.data);
          } else if (msg.type === 'done') {
            this.appendOutput('info', 'Session ended.');
          }
        } catch (e) {
          this.appendOutput('stdout', event.data);
        }
      };

      ws.onerror = (err) => {
        this.appendOutput('error', 'WebSocket error. Check console for details.');
        console.error('GCS interactive WS error:', err);
      };

      ws.onclose = () => {
        this.appendOutput('info', 'Interactive session closed.');
        this.interactiveWs = null;
      };

      this.interactiveWs = ws;
      return ws;
    },

    sendInteractiveInput(text) {
      if (this.interactiveWs && this.interactiveWs.readyState === WebSocket.OPEN) {
        // Append newline so the container's stdin readline() receives the input
        this.interactiveWs.send(JSON.stringify({ type: 'stdin', data: withNewline(text) }));
      }
    },

    sendInteractiveExec(cmd) {
      if (this.interactiveWs && this.interactiveWs.readyState === WebSocket.OPEN) {
        this.interactiveWs.send(JSON.stringify({ type: 'exec', cmd }));
      }
    },

    disconnectInteractive() {
      if (this.interactiveWs) {
        this.interactiveWs.close();
        this.interactiveWs = null;
      }
    },

    // -----------------------------------------------------------------------
    // Navigation helpers
    // -----------------------------------------------------------------------
    goToStep(step) {
      this.currentStep = step;
      this.clearOutput();
    },

    resetWizard() {
      this.currentService = null;
      this.currentStep = 0;
      this.clearOutput();
      this.error = null;
      this.disconnectInteractive();
    },

    // -----------------------------------------------------------------------
    // Internal helpers
    // -----------------------------------------------------------------------
    _stepFromStatus(status) {
      const map = {
        pending: 1,
        auth_complete: 2,
        endpoint_configured: 3,
        node_configured: 4,
        gateway_configured: 5,
        collections_configured: 5,
        complete: 5,
        error: 2,
      };
      return map[status] ?? 1;
    },
  },
});
