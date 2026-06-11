<template>
  <div class="overflow-x-auto">
    <table class="min-w-full divide-y divide-gray-200">
      <thead class="bg-gray-50">
        <tr>
          <th
            v-for="col in columns"
            :key="col.key"
            class="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider"
            :class="[
              col.sortable ? 'cursor-pointer select-none text-gray-600 hover:text-gray-900' : 'text-gray-500',
            ]"
            @click="col.sortable && toggleSort(col.key)"
          >
            <div class="flex items-center gap-1">
              {{ col.label }}
              <template v-if="col.sortable">
                <svg
                  v-if="sortKey === col.key"
                  class="h-4 w-4"
                  :class="sortDir === 'asc' ? '' : 'rotate-180'"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 15l7-7 7 7" />
                </svg>
                <svg
                  v-else
                  class="h-4 w-4 text-gray-300"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 16V4m0 0L3 8m4-4l4 4m6 0v12m0 0l4-4m-4 4l-4-4" />
                </svg>
              </template>
            </div>
          </th>
        </tr>
      </thead>
      <tbody class="divide-y divide-gray-200 bg-white">
        <!-- Loading state -->
        <tr v-if="loading">
          <td :colspan="columns.length" class="px-6 py-12 text-center">
            <div class="flex items-center justify-center gap-2 text-gray-500">
              <svg class="h-5 w-5 animate-spin" fill="none" viewBox="0 0 24 24">
                <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
                <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
              </svg>
              Loading...
            </div>
          </td>
        </tr>
        <!-- Empty state -->
        <tr v-else-if="!sortedRows.length">
          <td :colspan="columns.length" class="px-6 py-12 text-center text-gray-500">
            <slot name="empty">
              No data available.
            </slot>
          </td>
        </tr>
        <!-- Data rows -->
        <tr
          v-else
          v-for="(row, idx) in sortedRows"
          :key="row.id || idx"
          class="hover:bg-gray-50 transition-colors"
          @click="$emit('row-click', row)"
        >
          <td
            v-for="col in columns"
            :key="col.key"
            class="whitespace-nowrap px-6 py-4 text-sm text-gray-900"
          >
            <slot :name="`cell-${col.key}`" :row="row" :value="row[col.key]">
              {{ row[col.key] }}
            </slot>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'

const props = defineProps({
  columns: {
    type: Array,
    required: true,
    validator: (v) => v.every((c) => c.key && c.label),
  },
  rows: {
    type: Array,
    default: () => [],
  },
  loading: {
    type: Boolean,
    default: false,
  },
})

defineEmits(['row-click'])

const sortKey = ref(null)
const sortDir = ref('asc')

function toggleSort(key) {
  if (sortKey.value === key) {
    sortDir.value = sortDir.value === 'asc' ? 'desc' : 'asc'
  } else {
    sortKey.value = key
    sortDir.value = 'asc'
  }
}

const sortedRows = computed(() => {
  if (!sortKey.value) return props.rows
  const dir = sortDir.value === 'asc' ? 1 : -1
  return [...props.rows].sort((a, b) => {
    const aVal = a[sortKey.value] ?? ''
    const bVal = b[sortKey.value] ?? ''
    if (typeof aVal === 'number' && typeof bVal === 'number') {
      return (aVal - bVal) * dir
    }
    return String(aVal).localeCompare(String(bVal)) * dir
  })
})
</script>
