import { defineStore } from 'pinia';
import api from '../api';

export const useProfileStore = defineStore('profile', {
  state: () => ({
    profiles: [],
    networks: [],
    volumes: [],
    choices: {
        qos: [],
        networks: [],
        volumes: []
    },
    loading: false,
    error: null,
  }),
  actions: {
    async fetchAll(refresh = false) {
      this.loading = true;
      try {
        const [hostRes, netRes, volRes, choicesRes] = await Promise.all([
          api.getProfiles('host', refresh),
          api.getProfiles('network', refresh),
          api.getProfiles('volume', refresh),
          api.getProfileChoices()
        ]);
        this.profiles = hostRes.data.profiles;
        this.networks = netRes.data.profiles;
        this.volumes = volRes.data.profiles;
        this.choices = choicesRes.data;
        this.error = null;
      } catch (err) {
        this.error = 'Failed to fetch profiles';
      } finally {
        this.loading = false;
      }
    },
    async createProfile(resource, data) {
      try {
        await api.createProfile(resource, data);
        await this.fetchAll();
        return { success: true };
      } catch (err) {
        return { success: false, error: err.response?.data?.error || 'Failed to create profile' };
      }
    },
    async updateProfile(resource, data) {
      try {
        await api.updateProfile(resource, data);
        await this.fetchAll();
        return { success: true };
      } catch (err) {
        return { success: false, error: err.response?.data?.error || 'Failed to update profile' };
      }
    },
    async deleteProfile(resource, pname) {
      try {
        await api.deleteProfile(resource, pname);
        await this.fetchAll();
        return { success: true };
      } catch (err) {
        return { success: false, error: err.response?.data?.error || 'Failed to delete profile' };
      }
    }
  }
});
