<template>
  <div class="command-output-panel">
    <div class="panel-header d-flex justify-content-between align-items-center px-3 py-2 bg-dark rounded-top">
      <span class="text-white small font-weight-bold text-uppercase">
        <i class="fas fa-terminal mr-2"></i>Command Output
      </span>
      <div>
        <button class="btn btn-xs btn-outline-secondary" @click="$emit('clear')" title="Clear output">
          <i class="fas fa-trash-alt"></i>
        </button>
      </div>
    </div>

    <!-- Output area -->
    <div
      ref="outputEl"
      class="output-body p-3 rounded-bottom"
      :style="{
        height: height,
        overflowY: 'auto',
        fontFamily: 'monospace',
        fontSize: '0.85rem',
        whiteSpace: 'pre-wrap',
        wordBreak: 'break-all',
        backgroundColor: '#1e1e1e',
        color: '#d4d4d4',
      }"
    >
      <div v-if="lines.length === 0" style="color: #888;">
        <em>No output yet.</em>
      </div>
      <div
        v-for="(line, idx) in lines"
        :key="idx"
        :style="lineStyle(line.type)"
      >{{ stripAnsi(line.text) }}</div>
      <div v-if="loading" style="color: #f0ad4e;" class="mt-1">
        <i class="fas fa-spinner fa-spin mr-1"></i><em>Running...</em>
      </div>
    </div>

    <!-- Stdin input bar (for interactive sessions) — always visible when allowInput -->
    <div v-if="allowInput" class="input-group mt-2">
      <div class="input-group-prepend">
        <span class="input-group-text bg-dark text-warning border-secondary" style="font-size:0.75rem;">
          <i class="fas fa-keyboard mr-1"></i>stdin
        </span>
      </div>
      <input
        ref="stdinEl"
        v-model="stdinInput"
        type="text"
        class="form-control form-control-sm bg-dark text-white border-secondary"
        placeholder="Paste auth code or type input, then press Enter..."
        @keydown.enter="sendInput"
        style="font-family: monospace;"
      />
      <div class="input-group-append">
        <button class="btn btn-sm btn-outline-warning" @click="sendInput" title="Send">
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
const stdinEl = ref(null);
const stdinInput = ref('');

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

// Auto-focus the stdin input when allowInput becomes true
watch(
  () => props.allowInput,
  async (val) => {
    if (val) {
      await nextTick();
      stdinEl.value?.focus();
    }
  },
  { immediate: true }
);

// Strip ANSI escape sequences (color codes, cursor movement, progress bars, etc.)
// Covers: CSI sequences (\x1b[...m), OSC, cursor visibility (\x1b[?25l/h), etc.
function stripAnsi(text) {
  if (!text) return text;
  // eslint-disable-next-line no-control-regex
  return text.replace(/\x1b\[[0-9;?]*[a-zA-Z]/g, '')   // CSI sequences
             .replace(/\x1b\][^\x07]*\x07/g, '')         // OSC sequences
             .replace(/\x1b[()][AB012]/g, '')             // charset sequences
             .replace(/\x1b[DABC]/g, '')                  // cursor movement
             .replace(/\r/g, '');                          // carriage returns
}

function lineStyle(type) {
  switch (type) {
    case 'error':  return { color: '#f44747' };
    case 'info':   return { color: '#9cdcfe' };
    case 'stderr': return { color: '#ce9178' };
    default:       return { color: '#d4d4d4' };
  }
}

function sendInput() {
  const text = stdinInput.value;
  if (!text) return;
  emit('send-input', text);
  stdinInput.value = '';
  // Keep focus on the input for rapid successive entries
  nextTick(() => stdinEl.value?.focus());
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
