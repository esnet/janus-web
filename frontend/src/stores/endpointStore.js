import { defineStore } from 'pinia';
import api from '../api';

export const useEndpointStore = defineStore('endpoint', {
  state: () => ({
    nodes: [],
    nodeTypes: {},
    loading: false,
    error: null,
  }),
  actions: {
    async fetchNodes(refresh = false) {
      this.loading = true;
      try {
        const response = await api.getNodes(refresh);
        this.nodes = response.data.nodes;
        this.error = null;
      } catch (err) {
        this.error = 'Failed to fetch nodes';
        console.error(err);
      } finally {
        this.loading = false;
      }
    },
    async fetchNodeTypes() {
      try {
        const response = await api.getNodeTypes();
        this.nodeTypes = response.data;
      } catch (err) {
        console.error('Failed to fetch node types', err);
      }
    },
    async addNode(data) {
      this.loading = true;
      try {
        await api.addNode(data);
        await this.fetchNodes();
        return { success: true };
      } catch (err) {
        this.error = err.response?.data?.error || 'Failed to add node';
        return { success: false, error: this.error };
      } finally {
        this.loading = false;
      }
    },
    async removeNode(nname) {
      try {
        await api.removeNode(nname);
        await this.fetchNodes();
      } catch (err) {
        this.error = 'Failed to remove node';
      }
    }
  }
});
