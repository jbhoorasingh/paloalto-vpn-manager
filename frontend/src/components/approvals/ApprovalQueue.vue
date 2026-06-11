<template>
  <div class="space-y-4">
    <div class="flex items-center justify-end">
      <p class="text-sm text-gray-500">
        {{ requests.length }} request(s) awaiting review
      </p>
    </div>

    <DataTable
      :columns="columns"
      :rows="requests"
      :loading="loading"
      @row-click="handleRowClick"
    >
      <template #cell-status="{ value }">
        <StatusBadge :status="value" />
      </template>
      <template #cell-submitted_at="{ value }">
        {{ formatDate(value) }}
      </template>
      <template #cell-actions="{ row }">
        <a
          :href="`/vpn/requests/${row.id}/`"
          class="font-medium text-indigo-600 hover:text-indigo-500"
          @click.stop
        >
          Review
        </a>
      </template>
      <template #empty>
        <div class="text-center">
          <svg class="mx-auto h-10 w-10 text-gray-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <p class="mt-2 text-gray-500">No requests awaiting review.</p>
        </div>
      </template>
    </DataTable>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useApi } from '../../composables/useApi.js'
import DataTable from '../shared/DataTable.vue'
import StatusBadge from '../shared/StatusBadge.vue'

const { apiFetch, loading } = useApi()

const requests = ref([])

const columns = [
  { key: 'reference_number', label: 'Reference #', sortable: true },
  { key: 'title', label: 'Title', sortable: true },
  { key: 'vendor_name', label: 'Vendor', sortable: true },
  { key: 'requester', label: 'Requester', sortable: true },
  { key: 'status', label: 'Status', sortable: true },
  { key: 'submitted_at', label: 'Submitted', sortable: true },
  { key: 'actions', label: '', sortable: false },
]

function formatDate(dateStr) {
  if (!dateStr) return ''
  const d = new Date(dateStr)
  return d.toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  })
}

function handleRowClick(row) {
  window.location.href = `/vpn/requests/${row.id}/`
}

async function loadQueue() {
  const result = await apiFetch('/api/vpn/approvals/queue/')
  if (result.ok) {
    requests.value = result.data.requests || []
  }
}

onMounted(() => {
  loadQueue()
})
</script>
