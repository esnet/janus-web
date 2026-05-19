<template>
  <div class="command-output-panel">
    <div class="panel-header d-flex justify-content-between align-items-center px-3 py-2 bg-dark rounded-top">
      <span class="text-white small font-weight-bold text-uppercase">
        <i class="fas fa-terminal mr-2"></i>Command Output
      </span>
      <div>
        <button
          v-if="allowInput"
          class="btn btn-xs btn-outline-light mr-2"
          @click="showInputBar = !showInputBar"
          title="Toggle stdin input"
        >
          <i class="fas fa-keyboard"></i>
        </button>
        <button class="btn btn-xs btn-outline-secondary" @click="$emit('clear')" title="Clear output">
          <i class="fas fa-trash-alt"></i>
        </button>
      </div>
    </div>

    <!-- Output area -->
    <div
      ref="outputEl"
      class="output-body bg-black text-white p-3 rounded-bottom"
      :style="{ height: height, overflowY: 'auto', fontFamily: 'monospace', fontSize: '0.85rem', whiteSpace: 'pre-wrap', wordBreak: 'break-all' }"
    >
      <div v-if="lines.length === 0" class="text-muted">
        <em>No output yet.</em>
      </div>
      <div
        v-for="(line, idx) in lines"
        :key="idx"
        :class="lineClass(line.type)"
      >{{ line.text }}</div>
      <div v-if="loading" class="text-warning mt-1">
        <i class="fas fa-spinner fa-spin mr-1"></i><em>Running...</em>
      </div>
    </div>

    <!-- Stdin input bar (for interactive sessions) -->
    <div v-if="allowInput && showInputBar" class="input-group mt-2">
      <input
        v-model="stdinInput"
        type="text"
        class="form-control form-control-sm bg-dark text-white border-secondary"
        placeholder="Type input and press Enter..."
        @keydown.enter="sendInput"
        style="font-family: monospace;"
      />
      <div class="input-group-append">
        <button class="btn btn-sm btn-outline-warning" @click="sendInput">
          <i class="fas fa-paper-plane"></i>
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, nextTick } from 'vue';

const props = defineProps({
  lines: {
    type: Array,
    default: () => [],
    // Each element: { type: 'stdout'|'stderr'|'info'|'error', text: string }
  },
  loading: {
    type: Boolean,
    default: false,
  },
  height: {
    type: String,
    default: '300px',
  },
  allowInput: {
    type: Boolean,
    default: false,
  },
});

const emit = defineEmits(['clear', 'send-input']);

const outputEl = ref(null);
const stdinInput = ref('');
const showInputBar = ref(false);

// Auto-scroll to bottom when new lines arrive
watch(
  () => props.lines.length,
  async () => {
    await nextTick();
    if (outputEl.value) {
      outputEl.value.scrollTop = outputEl.value.scrollHeight;
    }
  }
);

function lineClass(type) {
  switch (type) {
    case 'error':  return 'text-danger';
    case 'info':   return 'text-info';
    case 'stderr': return 'text-warning';
    default:       return 'text-white';
  }
}

function sendInput() {
  const text = stdinInput.value;
  if (!text) return;
  emit('send-input', text);
  stdinInput.value = '';
}
</script>

<style scoped>
.command-output-panel {
  border-radius: 6px;
  overflow: hidden;
}
.btn-xs {
  padding: 0.1rem 0.4rem;
  font-size: 0.75rem;
}
</style>
