<template>
  <div class="d-flex justify-content-between align-items-center p-3 bg-light border-top">
    <div class="d-flex align-items-center">
      <div class="small text-muted mr-3">
        Show
        <select class="custom-select custom-select-sm d-inline-block mx-1" style="width: auto"
                :value="pageSize" @change="onPageSizeChange($event.target.value)">
          <option v-for="opt in pageSizeOptions" :key="opt" :value="opt">{{ opt }}</option>
        </select>
        per page
      </div>
      <div class="small text-muted" v-if="totalItems > 0">
        Showing <b>{{ startItem }}</b> to <b>{{ endItem }}</b> of <b>{{ totalItems }}</b> entries
      </div>
    </div>
    <nav aria-label="Page navigation" v-if="totalPages > 1">
      <ul class="pagination pagination-sm mb-0 shadow-sm">
        <li class="page-item" :class="{ disabled: currentPage === 1 }">
          <a class="page-link" href="#" @click.prevent="setPage(1)" aria-label="First">
            <i class="fas fa-angle-double-left"></i>
          </a>
        </li>
        <li class="page-item" :class="{ disabled: currentPage === 1 }">
          <a class="page-link" href="#" @click.prevent="setPage(currentPage - 1)" aria-label="Previous">
            <i class="fas fa-angle-left"></i>
          </a>
        </li>
        
        <li v-for="page in visiblePages" :key="page" class="page-item" :class="{ active: currentPage === page }">
          <a class="page-link" href="#" @click.prevent="setPage(page)">{{ page }}</a>
        </li>

        <li class="page-item" :class="{ disabled: currentPage === totalPages }">
          <a class="page-link" href="#" @click.prevent="setPage(currentPage + 1)" aria-label="Next">
            <i class="fas fa-angle-right"></i>
          </a>
        </li>
        <li class="page-item" :class="{ disabled: currentPage === totalPages }">
          <a class="page-link" href="#" @click.prevent="setPage(totalPages)" aria-label="Last">
            <i class="fas fa-angle-double-right"></i>
          </a>
        </li>
      </ul>
    </nav>
  </div>
</template>

<script setup>
import { computed } from 'vue';

const pageSizeOptions = [10, 20, 50, 100];

const props = defineProps({
  currentPage: { type: Number, required: true },
  totalItems: { type: Number, required: true },
  pageSize: { type: Number, default: 20 }
});

const emit = defineEmits(['update:currentPage', 'update:pageSize']);

const totalPages = computed(() => Math.ceil(props.totalItems / props.pageSize));
const startItem = computed(() => ((props.currentPage - 1) * props.pageSize) + 1);
const endItem = computed(() => Math.min(props.currentPage * props.pageSize, props.totalItems));

const visiblePages = computed(() => {
  const pages = [];
  const maxVisible = 5;
  let start = Math.max(1, props.currentPage - 2);
  let end = Math.min(totalPages.value, start + maxVisible - 1);
  
  if (end - start + 1 < maxVisible) {
    start = Math.max(1, end - maxVisible + 1);
  }
  
  for (let i = start; i <= end; i++) {
    pages.push(i);
  }
  return pages;
});

const setPage = (page) => {
  if (page >= 1 && page <= totalPages.value) {
    emit('update:currentPage', page);
  }
};

const onPageSizeChange = (value) => {
  const newSize = Number(value);
  emit('update:pageSize', newSize);
  emit('update:currentPage', 1);
};
</script>

<style scoped>
.pagination .page-link {
    color: #495057;
    border: 1px solid #dee2e6;
}
.pagination .page-item.active .page-link {
    background-color: #007bff;
    border-color: #007bff;
    color: white;
}
.pagination .page-item.disabled .page-link {
    background-color: #fff;
    color: #adb5bd;
}
</style>
