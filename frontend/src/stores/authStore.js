import { defineStore } from 'pinia';
import api from '../api';

export const useAuthStore = defineStore('auth', {
  state: () => ({
    users: [],
    groups: [],
    nodes: [],
    profiles: [],
    images: [],
    sessions: [],
    loading: false,
    error: null,
  }),
  actions: {
    async fetchAccessInfo() {
      this.loading = true;
      try {
        const response = await api.getAccessInfo();
        this.users = response.data.users;
        this.groups = response.data.groups;
        this.nodes = response.data.nodes;
        this.profiles = response.data.profiles;
        this.images = response.data.images;
        this.sessions = response.data.sessions;
        this.error = null;
      } catch (err) {
        this.error = 'Failed to fetch access control info';
        console.error(err);
      } finally {
        this.loading = false;
      }
    },
    async updateAccess(resource, identifier, selectedUsers, selectedGroups, remove = false) {
      try {
        await api.updateAccess({
          resource,
          identifier,
          users: selectedUsers,
          groups: selectedGroups,
          remove
        });
        await this.fetchAccessInfo();
        return { success: true };
      } catch (err) {
        return { 
            success: false, 
            error: err.response?.data?.result?.message || 'Failed to update access control' 
        };
      }
    },
    async updateAccessBulk(resource, identifiers, selectedUsers, selectedGroups, remove = false) {
      try {
        await api.updateAccessBulk({
          resource,
          identifiers,
          users: selectedUsers,
          groups: selectedGroups,
          remove
        });
        await this.fetchAccessInfo();
        return { success: true };
      } catch (err) {
        return { 
            success: false, 
            error: err.response?.data?.result?.message || 'Failed to update access control' 
        };
      }
    }
  }
});
