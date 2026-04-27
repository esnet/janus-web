import { createApp } from 'vue';
import { createPinia } from 'pinia';
import SessionDashboard from './components/SessionDashboard.vue';
import EndpointDashboard from './components/EndpointDashboard.vue';
import ProfileDashboard from './components/ProfileDashboard.vue';

const pinia = createPinia();

const mountComponent = (id, component) => {
  const el = document.getElementById(id);
  if (el) {
    const app = createApp(component);
    app.use(pinia);
    app.mount(el);
  }
};

mountComponent('session-dashboard', SessionDashboard);
mountComponent('endpoint-dashboard', EndpointDashboard);
mountComponent('profile-dashboard', ProfileDashboard);
