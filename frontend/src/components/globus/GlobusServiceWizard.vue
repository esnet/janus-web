<template>
  <div class="container-fluid" style="padding-top: 2%">
    <!-- Error banner -->
    <div v-if="store.error && !store.loading" class="alert alert-danger shadow-sm" role="alert">
      <i class="fas fa-exclamation-triangle mr-2"></i><b>{{ store.error }}</b>
    </div>

    <!-- Step 0: Select session / container -->
    <div v-if="store.currentStep === 0">
      <SessionSelectorPane @selected="handleSessionSelected" />
    </div>

    <!-- Steps 1–5: Main wizard -->
    <div v-else>
      <!-- Progress bar -->
      <div class="card border-0 shadow-sm mb-4">
        <div class="card-body py-3">
          <div class="d-flex align-items-center justify-content-between mb-2">
            <h5 class="mb-0 font-weight-bold">
              <i class="fas fa-cogs mr-2 text-warning"></i>
              Globus Connect Server Setup
            </h5>
            <div class="text-muted small">
              Step {{ store.currentStep }} of {{ steps.length }}
            </div>
          </div>

          <!-- Step indicators -->
          <div class="d-flex align-items-center mt-3">
            <template v-for="(step, idx) in steps" :key="idx">
              <div
                class="step-indicator d-flex flex-column align-items-center"
                :class="stepIndicatorClass(idx + 1)"
                style="flex: 1; cursor: pointer;"
                @click="tryNavigateToStep(idx + 1)"
              >
                <div
                  class="step-circle d-flex align-items-center justify-content-center rounded-circle mb-1"
                  :class="stepCircleClass(idx + 1)"
                  style="width: 36px; height: 36px; font-size: 0.85rem; font-weight: bold;"
                >
                  <i v-if="isStepComplete(idx + 1)" class="fas fa-check"></i>
                  <span v-else>{{ idx + 1 }}</span>
                </div>
                <div class="text-center" style="font-size: 0.7rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em;">
                  {{ step.label }}
                </div>
              </div>
              <div
                v-if="idx < steps.length - 1"
                class="step-connector flex-grow-1"
                :class="idx + 1 < store.currentStep ? 'bg-success' : 'bg-light'"
                style="height: 3px; margin-bottom: 20px;"
              ></div>
            </template>
          </div>
        </div>
      </div>

      <!-- Service info bar -->
      <div v-if="store.currentService" class="alert alert-light border d-flex align-items-center mb-3 py-2">
        <i class="fas fa-info-circle text-primary mr-2"></i>
        <span class="small">
          <strong>Service:</strong> {{ store.currentService.display_name || '(unnamed)' }}
          &nbsp;&mdash;&nbsp;
          <strong>Session:</strong> {{ store.currentService.session_id }}
          &nbsp;&mdash;&nbsp;
          <strong>Status:</strong>
          <span :class="statusBadgeClass(store.currentService.status)" class="badge ml-1">
            {{ store.currentService.status }}
          </span>
        </span>
        <button
          class="btn btn-sm btn-link text-danger ml-auto"
          @click="confirmReset"
          title="Abandon this service and start over"
        >
          <i class="fas fa-times"></i> Reset
        </button>
      </div>

      <!-- Step panes -->
      <GlobusAuthPane
        v-if="store.currentStep === 1"
        @next="store.goToStep(2)"
      />
      <EndpointConfigPane
        v-else-if="store.currentStep === 2"
        @next="store.goToStep(3)"
        @back="store.goToStep(1)"
      />
      <NodeConfigPane
        v-else-if="store.currentStep === 3"
        @next="store.goToStep(4)"
        @back="store.goToStep(2)"
      />
      <StorageGatewayPane
        v-else-if="store.currentStep === 4"
        @next="store.goToStep(5)"
        @back="store.goToStep(3)"
      />
      <CollectionsPane
        v-else-if="store.currentStep === 5"
        @back="store.goToStep(4)"
        @finish="handleFinish"
      />
    </div>
  </div>
</template>

<script setup>
import { onMounted } from 'vue';
import { useGlobusServiceStore } from '../../stores/globusServiceStore';
import SessionSelectorPane from './SessionSelectorPane.vue';
import GlobusAuthPane from './GlobusAuthPane.vue';
import EndpointConfigPane from './EndpointConfigPane.vue';
import NodeConfigPane from './NodeConfigPane.vue';
import StorageGatewayPane from './StorageGatewayPane.vue';
import CollectionsPane from './CollectionsPane.vue';

const store = useGlobusServiceStore();

// Restore wizard state from sessionStorage on page load.
// This handles the case where the user was redirected to Globus Auth
// and the page reloaded on the callback URL.
async function restoreStateFromSession() {
  // Clear any stale sessionStorage from previous redirect-based auth flow
  sessionStorage.removeItem('gcs_service_id');
  sessionStorage.removeItem('gcs_wizard_step');

  // Check for ?resume=<service_id> in the URL (from Services dashboard "Resume" button)
  const params = new URLSearchParams(window.location.search);
  const resumeId = params.get('resume');
  if (resumeId) {
    // Clean the URL
    window.history.replaceState({}, document.title, window.location.pathname);
    // loadService() already calls _stepFromStatus() and sets store.currentStep
    await store.loadService(parseInt(resumeId));
  }
}

const steps = [
  { label: 'Auth' },
  { label: 'Endpoint' },
  { label: 'Node' },
  { label: 'Gateway' },
  { label: 'Collections' },
];

// Status → step number mapping (step is complete if service status is past it)
const statusOrder = {
  pending: 0,
  auth_complete: 1,
  endpoint_configured: 2,
  node_configured: 3,
  gateway_configured: 4,
  collections_configured: 5,
  complete: 5,
};

onMounted(async () => {
  // Restore wizard state first (handles Globus auth redirect)
  await restoreStateFromSession();
  await store.checkAuthStatus();
});

function isStepComplete(stepNum) {
  const svcStatus = store.currentService?.status;
  if (!svcStatus) return false;
  return (statusOrder[svcStatus] ?? 0) >= stepNum;
}

function stepIndicatorClass(stepNum) {
  if (store.currentStep === stepNum) return 'text-primary';
  if (isStepComplete(stepNum)) return 'text-success';
  return 'text-muted';
}

function stepCircleClass(stepNum) {
  if (store.currentStep === stepNum) return 'bg-primary text-white';
  if (isStepComplete(stepNum)) return 'bg-success text-white';
  return 'bg-light text-muted border';
}

function tryNavigateToStep(stepNum) {
  // Only allow navigating to completed steps or the current step
  if (stepNum <= store.currentStep || isStepComplete(stepNum - 1)) {
    store.goToStep(stepNum);
  }
}

function statusBadgeClass(status) {
  const map = {
    pending: 'badge-secondary',
    auth_complete: 'badge-info',
    endpoint_configured: 'badge-primary',
    node_configured: 'badge-primary',
    gateway_configured: 'badge-warning',
    collections_configured: 'badge-success',
    complete: 'badge-success',
    error: 'badge-danger',
  };
  return map[status] || 'badge-secondary';
}

function handleSessionSelected({ sessionId, nodeName, containerId, displayName }) {
  store.createService(sessionId, nodeName, containerId, displayName).then((result) => {
    if (result.success) {
      store.currentStep = 1;
    }
  });
}

function handleFinish() {
  // Navigate to the services list page
  window.location.href = '/janus/services/';
}

function confirmReset() {
  if (confirm('Are you sure you want to abandon this service configuration and start over?')) {
    store.resetWizard();
  }
}
</script>

<style scoped>
.step-indicator {
  transition: color 0.2s;
}
.step-circle {
  transition: background-color 0.2s, color 0.2s;
}
.step-connector {
  transition: background-color 0.2s;
}
</style>
