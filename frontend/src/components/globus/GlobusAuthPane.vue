<template>
  <div class="globus-auth-pane">
    <!-- Already authenticated -->
    <div v-if="store.isAuthenticated" class="text-center py-4">
      <div class="mb-3">
        <i class="fas fa-check-circle fa-3x text-success"></i>
      </div>
      <h5 class="font-weight-bold">Authenticated with Globus</h5>
      <p class="text-muted">Your Globus credentials are stored and ready for use.</p>
      <div class="d-flex justify-content-center mt-3">
        <button class="btn btn-success" @click="$emit('next')">
          <i class="fas fa-arrow-right mr-1"></i> Continue to Endpoint Setup
        </button>
        <button class="btn btn-outline-secondary ml-2" @click="handleLogout">
          <i class="fas fa-sign-out-alt mr-1"></i> Re-authenticate
        </button>
      </div>
    </div>

    <!-- Auth flow -->
    <div v-else class="card border-0 shadow-sm p-4">
      <div class="d-flex align-items-center mb-3">
        <i class="fas fa-globe fa-2x text-primary mr-3"></i>
        <h5 class="font-weight-bold mb-0">Authenticate with Globus</h5>
      </div>

      <p class="text-muted small mb-4">
        To configure a Globus Connect Server endpoint, you must authenticate with your
        Globus account. Click the button below to get your authorization URL, open it
        in your browser, authenticate, then paste the resulting code here.
      </p>

      <!-- Step 1: Get auth URL -->
      <div v-if="!authUrl" class="mb-3">
        <button
          class="btn btn-primary"
          :disabled="loading"
          @click="getAuthUrl"
        >
          <span v-if="loading">
            <i class="fas fa-spinner fa-spin mr-1"></i> Loading...
          </span>
          <span v-else>
            <i class="fas fa-key mr-1"></i> Get Globus Authorization URL
          </span>
        </button>
      </div>

      <!-- Step 2: Show URL and code input -->
      <div v-if="authUrl">
        <div class="alert alert-info small py-2 mb-3">
          <i class="fas fa-info-circle mr-1"></i>
          <strong>Step 1:</strong> Open the URL below in your browser and authenticate with Globus.
        </div>

        <div class="form-group">
          <label class="font-weight-bold small text-uppercase text-muted">Authorization URL</label>
          <div class="input-group">
            <input
              :value="authUrl"
              type="text"
              class="form-control form-control-sm bg-light"
              readonly
              ref="urlInput"
            />
            <div class="input-group-append">
              <button class="btn btn-sm btn-outline-secondary" @click="copyUrl" title="Copy URL">
                <i class="fas" :class="copied ? 'fa-check text-success' : 'fa-copy'"></i>
              </button>
              <a :href="authUrl" target="_blank" rel="noopener noreferrer" class="btn btn-sm btn-outline-primary">
                <i class="fas fa-external-link-alt"></i> Open
              </a>
            </div>
          </div>
        </div>

        <div class="alert alert-info small py-2 mb-3">
          <i class="fas fa-info-circle mr-1"></i>
          <strong>Step 2:</strong> After authenticating, Globus will show you an authorization code.
          Copy it and paste it below.
        </div>

        <div class="form-group">
          <label class="font-weight-bold small text-uppercase text-muted">
            Authorization Code <span class="text-danger">*</span>
          </label>
          <input
            v-model="authCode"
            type="text"
            class="form-control"
            placeholder="Paste the authorization code from Globus here..."
            :disabled="loading"
            @keydown.enter="submitCode"
          />
        </div>

        <div v-if="error" class="alert alert-danger small py-2">
          <i class="fas fa-exclamation-triangle mr-1"></i>{{ error }}
        </div>

        <div class="d-flex align-items-center mt-2">
          <button
            class="btn btn-primary"
            :disabled="!authCode.trim() || loading"
            @click="submitCode"
          >
            <span v-if="loading">
              <i class="fas fa-spinner fa-spin mr-1"></i> Verifying...
            </span>
            <span v-else>
              <i class="fas fa-check mr-1"></i> Submit Code
            </span>
          </button>
          <button class="btn btn-link text-muted ml-2" @click="reset">
            Start over
          </button>
        </div>
      </div>

      <div v-if="error && !authUrl" class="alert alert-danger small py-2 mt-3">
        <i class="fas fa-exclamation-triangle mr-1"></i>{{ error }}
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue';
import { useGlobusServiceStore } from '../../stores/globusServiceStore';

const emit = defineEmits(['next']);

const store = useGlobusServiceStore();
const authUrl = ref('');
const authCode = ref('');
const loading = ref(false);
const error = ref('');
const copied = ref(false);
const urlInput = ref(null);

onMounted(async () => {
  await store.checkAuthStatus();
  // Clear any stale sessionStorage from previous redirect-based flow
  sessionStorage.removeItem('gcs_wizard_step');
});

async function getAuthUrl() {
  error.value = '';
  loading.value = true;
  try {
    const result = await store.getAuthUrl();
    if (result.success) {
      authUrl.value = result.authUrl;
    } else {
      error.value = result.error;
    }
  } finally {
    loading.value = false;
  }
}

async function copyUrl() {
  try {
    await navigator.clipboard.writeText(authUrl.value);
    copied.value = true;
    setTimeout(() => { copied.value = false; }, 2000);
  } catch {
    // Fallback: select the input
    if (urlInput.value) urlInput.value.select();
  }
}

async function submitCode() {
  error.value = '';
  if (!authCode.value.trim()) {
    error.value = 'Please paste the authorization code.';
    return;
  }
  loading.value = true;
  try {
    const result = await store.exchangeCode(authCode.value.trim(), '');
    if (result.success) {
      authCode.value = '';
      authUrl.value = '';
    } else {
      error.value = result.error;
    }
  } finally {
    loading.value = false;
  }
}

function reset() {
  authUrl.value = '';
  authCode.value = '';
  error.value = '';
}

async function handleLogout() {
  await store.globusLogout();
  authUrl.value = '';
  authCode.value = '';
  error.value = '';
}
</script>
