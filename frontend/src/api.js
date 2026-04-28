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
  }
};
