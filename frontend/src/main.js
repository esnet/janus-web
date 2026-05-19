import { createApp } from 'vue';
import { createPinia } from 'pinia';
import SessionDashboard from './components/SessionDashboard.vue';
import EndpointDashboard from './components/EndpointDashboard.vue';
import ProfileDashboard from './components/ProfileDashboard.vue';
import AccessControlDashboard from './components/AccessControlDashboard.vue';
import ServicesDashboard from './components/globus/ServicesDashboard.vue';
import GlobusServiceWizard from './components/globus/GlobusServiceWizard.vue';

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
mountComponent('access-control-dashboard', AccessControlDashboard);
mountComponent('services-dashboard', ServicesDashboard);
mountComponent('globus-service-wizard', GlobusServiceWizard);
