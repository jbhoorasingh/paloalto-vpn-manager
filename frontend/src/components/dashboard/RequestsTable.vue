<template>
  <div class="space-y-4">
    <!-- Filter bar -->
    <div class="flex items-center justify-between">
      <div class="flex items-center gap-3">
        <label for="status-filter" class="text-sm font-medium text-gray-700">Filter by status:</label>
        <select
          id="status-filter"
          v-model="statusFilter"
          class="rounded-md border-gray-300 text-sm shadow-sm focus:border-indigo-500 focus:ring-indigo-500"
        >
          <option value="">All Statuses</option>
          <option value="draft">Draft</option>
          <option value="submitted">Submitted</option>
          <option value="infosec_approved">InfoSec Approved</option>
          <option value="infosec_changes_requested">InfoSec Changes Requested</option>
          <option value="network_approved">Network Approved</option>
          <option value="network_changes_requested">Network Changes Requested</option>
          <option value="rejected">Rejected</option>
          <option value="active">Active</option>
          <option value="scheduled">Scheduled</option>
          <option value="deployed">Deployed</option>
          <option value="decommissioned">Decommissioned</option>
        </select>
      </div>
      <p class="text-sm text-gray-500">
        {{ filteredRequests.length }} request(s)
      </p>
    </div>

    <!-- Table -->
    <DataTable
      :columns="columns"
      :rows="filteredRequests"
      :loading="loading"
      @row-click="handleRowClick"
    >
      <template #cell-status="{ value }">
        <StatusBadge :status="value" />
      </template>
      <template #cell-created_at="{ value }">
        {{ formatDate(value) }}
      </template>
      <template #cell-actions="{ row }">
        <a
          :href="`/vpn/requests/${row.id}/`"
          class="font-medium text-indigo-600 hover:text-indigo-500"
          @click.stop
        >
          View
        </a>
      </template>
      <template #empty>
        <div class="text-center">
          <svg class="mx-auto h-10 w-10 text-gray-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
          </svg>
          <p class="mt-2 text-gray-500">No VPN requests found.</p>
        </div>
      </template>
    </DataTable>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useApi } from '../../composables/useApi.js'
import DataTable from '../shared/DataTable.vue'
import StatusBadge from '../shared/StatusBadge.vue'

const props = defineProps({
  scope: {
    type: String,
    default: 'mine',
  },
})

const { apiFetch, loading } = useApi()

const localRequests = ref([])
const statusFilter = ref('')

const columns = [
  { key: 'reference_number', label: 'Reference #', sortable: true },
  { key: 'title', label: 'Title', sortable: true },
  { key: 'vendor_name', label: 'Vendor', sortable: true },
  { key: 'status', label: 'Status', sortable: true },
  { key: 'created_at', label: 'Created', sortable: true },
  { key: 'actions', label: '', sortable: false },
]

const filteredRequests = computed(() => {
  if (!statusFilter.value) return localRequests.value
  return localRequests.value.filter((r) => r.status === statusFilter.value)
})

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

async function loadRequests() {
  const url = `/api/vpn/requests/?scope=${props.scope}`
  const result = await apiFetch(url)
  if (result.ok) {
    localRequests.value = result.data.requests || []
  }
}

onMounted(() => {
  loadRequests()
})
</script>
