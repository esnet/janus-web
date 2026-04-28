import { defineStore } from 'pinia';
import api from '../api';

export const useSessionStore = defineStore('session', {
  state: () => ({
    sessions: [],
    images: [],
    loading: false,
    error: null,
    ws: null,
  }),
  actions: {
    async fetchSessions() {
      this.loading = true;
      try {
        const response = await api.getSessions();
        this.sessions = response.data.sessions;
        this.error = null;
      } catch (err) {
        this.error = 'Failed to fetch sessions';
        console.error(err);
      } finally {
        this.loading = false;
      }
    },
    async fetchImages() {
      try {
        const response = await api.getImages();
        this.images = response.data.images;
      } catch (err) {
        console.error('Failed to fetch images', err);
      }
    },
    async createSession(data) {
      this.loading = true;
      try {
        await api.createSession(data);
        await this.fetchSessions();
        return { success: true };
      } catch (err) {
        this.error = err.response?.data?.error || 'Failed to create session';
        return { success: false, error: this.error };
      } finally {
        this.loading = false;
      }
    },
    async updateSession(id, data, apply = false) {
      this.loading = true;
      try {
        await api.updateSession(id, data, apply);
        await this.fetchSessions();
        return { success: true };
      } catch (err) {
        this.error = err.response?.data?.error || 'Failed to update session';
        return { success: false, error: this.error };
      } finally {
        this.loading = false;
      }
    },
    async applySessionChanges(id) {
      this.loading = true;
      try {
        await api.applySessionChanges(id);
        await this.fetchSessions();
        return { success: true };
      } catch (err) {
        this.error = err.response?.data?.error || 'Failed to apply changes';
        return { success: false, error: this.error };
      } finally {
        this.loading = false;
      }
    },

    async startSession(id) {
      try {
        await api.startSession(id);
        await this.fetchSessions();
      } catch (err) {
        this.error = 'Failed to start session';
      }
    },
    async stopSession(id) {
      try {
        await api.stopSession(id);
        await this.fetchSessions();
      } catch (err) {
        this.error = 'Failed to stop session';
      }
    },
    async deleteSession(id) {
      try {
        await api.deleteSession(id);
        await this.fetchSessions();
      } catch (err) {
        this.error = 'Failed to delete session';
      }
    },
    initWebSocket() {
      if (this.socket) return;

      const wsProtocol = window.location.protocol === 'https:' ? 'wss://' : 'ws://';
      const wsUrl = `${wsProtocol}${window.location.host}/ws/events/`;
      
      this.socket = new WebSocket(wsUrl);

      this.socket.onmessage = (event) => {
        const data = JSON.parse(event.data);
        console.log('WebSocket event received:', data);
        
        // Handle session state changes from the controller
        if (data && data.id && data.state) {
            this.updateSessionState(data.id, data.state);
        }
        
        // Potentially trigger a full refresh on major events
        if (data && (data.event === 'session_created' || data.event === 'session_deleted')) {
            this.fetchSessions();
        }
      };

      this.socket.onclose = () => {
        this.socket = null;
        // Reconnect after 5 seconds
        setTimeout(() => this.initWebSocket(), 5000);
      };
    },
    updateSessionState(id, newState) {
      const session = this.sessions.find(s => s.id === id);
      if (session) {
        session.state = newState;
      } else {
        // If we get an update for a session we don't know about, fetch all
        this.fetchSessions();
      }
    }
  }
});
