<template>
  <div class="modern-ui">
    <SessionDashboard />
  </div>
</template>

<script setup>
import SessionDashboard from './components/SessionDashboard.vue';
</script>

<style>
/* Global modernization styles */
body {
  background-color: #f4f7f6;
}

.modern-ui {
  font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
}

.badge {
  padding: 0.5em 0.8em;
  font-weight: 600;
  text-transform: uppercase;
  font-size: 0.75rem;
}

.table thead th {
  border-top: none;
  background-color: #f8f9fa;
  color: #495057;
  font-weight: 600;
  font-size: 0.85rem;
  text-transform: uppercase;
}

.table-striped tbody tr:nth-of-type(odd) {
  background-color: rgba(0, 0, 0, 0.02);
}

.accordion-toggle:hover {
  background-color: rgba(0, 123, 255, 0.05) !important;
}

pre, code {
  font-size: 0.9rem;
}
</style>
