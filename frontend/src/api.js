import axios from 'axios';

const api = axios.create({
  baseURL: '/janus/api/',
  timeout: 30000,
  headers: {
    'X-Requested-With': 'XMLHttpRequest',
  }
});

// Helper to get CSRF token from cookies
function getCookie(name) {
  let cookieValue = null;
  if (document.cookie && document.cookie !== '') {
    const cookies = document.cookie.split(';');
    for (let i = 0; i < cookies.length; i++) {
      const cookie = cookies[i].trim();
      if (cookie.substring(0, name.length + 1) === (name + '=')) {
        cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
        break;
      }
    }
  }
  return cookieValue;
}

api.interceptors.request.use((config) => {
  const csrftoken = getCookie('csrftoken');
  if (csrftoken) {
    config.headers['X-CSRFToken'] = csrftoken;
  }
  return config;
});

// Separate axios instance for the globus_service API (different URL prefix)
const globusApi = axios.create({
  baseURL: '/janus/services/',
  timeout: 120000,
  headers: {
    'X-Requested-With': 'XMLHttpRequest',
  }
});

globusApi.interceptors.request.use((config) => {
  const csrftoken = getCookie('csrftoken');
  if (csrftoken) {
    config.headers['X-CSRFToken'] = csrftoken;
  }
  return config;
});

export default {
  // Sessions
  getSessions() {
    return api.get('sessions/');
  },
  createSession(data) {
    return api.post('sessions/create/', data);
  },
  updateSession(id, data, apply = false) {
    return api.post(`sessions/${id}/update/?apply=${apply}`, data);
  },
  applySessionChanges(id) {
    return api.post(`sessions/${id}/apply/`);
  },
  startSession(id) {
    return api.post(`sessions/${id}/start/`);
  },
  stopSession(id) {
    return api.post(`sessions/${id}/stop/`);
  },
  deleteSession(id) {
    return api.post(`sessions/${id}/delete/`);
  },
  getLogs(sid, nname, timestamps = false) {
    return api.get(`sessions/${sid}/logs/${nname}/?timestamps=${timestamps}`);
  },

  // Endpoints (Nodes)
  getNodes(refresh = false) {
    return api.get(`nodes/?refresh=${refresh}`);
  },
  getNodeTypes() {
    return api.get('node-types/');
  },
  addNode(data) {
    return api.post('nodes/add/', data);
  },
  removeNode(nname) {
    return api.post(`nodes/remove/${nname}/`);
  },
  getImages() {
    return api.get('images/');
  },

  // Profiles
  getProfiles(resource, refresh = false) {
    return api.get(`profiles/${resource}/?refresh=${refresh}`);
  },
  getProfileChoices() {
    return api.get('profile-choices/');
  },
  createProfile(resource, data) {
    return api.post(`profiles/${resource}/create/`, data);
  },
  updateProfile(resource, data) {
    return api.post(`profiles/${resource}/update/`, data);
  },
  deleteProfile(resource, pname) {
    return api.post(`profiles/${resource}/delete/${pname}/`);
  },

  // Access Control (Authorization)
  getAccessInfo() {
    return axios.get('/authentication/api/access-info/');
  },
  updateAccess(data) {
    return axios.post('/authentication/api/update-access/', data, {
        headers: {
            'X-CSRFToken': getCookie('csrftoken')
        }
    });
  },
  updateAccessBulk(data) {
    return axios.post('/authentication/api/update-access-bulk/', data, {
        headers: {
            'X-CSRFToken': getCookie('csrftoken')
        }
    });
  },

  // -------------------------------------------------------------------------
  // Globus Service
  // -------------------------------------------------------------------------
  getGlobusServices() {
    return globusApi.get('api/globus/');
  },
  createGlobusService(data) {
    return globusApi.post('api/globus/create/', data);
  },
  getGlobusService(id) {
    return globusApi.get(`api/globus/${id}/`);
  },
  deleteGlobusService(id) {
    return globusApi.post(`api/globus/${id}/delete/`);
  },

  // Globus Auth
  getGlobusAuthUrl() {
    return globusApi.get('api/globus/auth/url/');
  },
  exchangeGlobusCode(data) {
    return globusApi.post('api/globus/auth/callback/', data);
  },
  getGlobusAuthStatus() {
    return globusApi.get('api/globus/auth/status/');
  },
  globusAuthLogout() {
    return globusApi.post('api/globus/auth/logout/');
  },

  // GCS wizard steps
  // Set endpoint ID manually (when auto-extraction fails)
  setGlobusEndpointId(id, endpointId) {
    return globusApi.post(`api/globus/${id}/endpoint/set-id/`, { endpoint_id: endpointId });
  },
  // Endpoint setup — returns command string for interactive WebSocket execution
  getEndpointSetupCmd(id, data) {
    return globusApi.post(`api/globus/${id}/endpoint/cmd/`, data);
  },
  // Collect deployment key after interactive endpoint setup
  fetchGlobusDeploymentKey(id, data) {
    return globusApi.post(`api/globus/${id}/endpoint/deployment-key/`, data);
  },
  // Transfer endpoint ownership to service account (interactive)
  setGlobusEndpointOwner(id, serviceAccountId) {
    return globusApi.post(`api/globus/${id}/endpoint/set-owner/`, { service_account_id: serviceAccountId });
  },
  // Legacy endpoint setup (non-interactive fallback)
  setupGlobusEndpoint(id, data) {
    return globusApi.post(`api/globus/${id}/endpoint/setup/`, data);
  },
  setupGlobusNode(id, data) {
    return globusApi.post(`api/globus/${id}/node/setup/`, data);
  },
  // GCS Login command (Step 3.5) — returns interactive `gcs login && set-owner` cmd string
  getGcsLoginCmd(id) {
    return globusApi.get(`api/globus/${id}/node/login-cmd/`);
  },
  // Storage gateway — service account REST API (no GCS login required)
  createGlobusGateway(id, data) {
    return globusApi.post(`api/globus/${id}/gateway/create/`, data);
  },
  listGateways(id) {
    return globusApi.get(`api/globus/${id}/gateway/list/`);
  },
  // Collections — service account REST API (mapped or guest)
  createGlobusCollection(id, data) {
    return globusApi.post(`api/globus/${id}/collection/create/`, data);
  },
  listCollections(id) {
    return globusApi.get(`api/globus/${id}/collection/list/`);
  },
  execGlobusCommand(id, cmd) {
    return globusApi.post(`api/globus/${id}/exec/`, { cmd });
  },
  // Grant a user administrator role on the endpoint (service account does this)
  grantUserAdmin(id, data) {
    return globusApi.post(`api/globus/${id}/endpoint/grant-admin/`, data);
  },
};
