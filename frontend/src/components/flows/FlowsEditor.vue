<template>
  <div class="space-y-4">
    <!-- Add button -->
    <div class="flex justify-end">
      <button
        v-if="!isAddingNew && !editingFlow"
        type="button"
        class="inline-flex items-center gap-1.5 rounded-md bg-indigo-600 px-3 py-2 text-sm font-medium text-white shadow-sm hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2"
        @click="addNewFlow"
      >
        <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" />
        </svg>
        Add Flow
      </button>
    </div>

    <!-- Add / edit form -->
    <FlowForm
      v-if="isAddingNew"
      :flow="newFlow"
      :is-new="true"
      @save="saveNewFlow"
      @cancel="cancelNewFlow"
    />
    <FlowForm
      v-else-if="editingFlow"
      :key="editingFlow.id"
      :flow="editingFlow"
      @save="saveExistingFlow"
      @cancel="editingFlow = null"
    />

    <!-- Loading state -->
    <div v-if="loading" class="flex items-center justify-center py-12 text-gray-500">
      <svg class="mr-2 h-5 w-5 animate-spin" fill="none" viewBox="0 0 24 24">
        <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
        <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
      </svg>
      Loading flows...
    </div>

    <!-- Error state -->
    <div v-else-if="error" class="rounded-md bg-red-50 p-4 text-sm text-red-700">
      {{ error }}
    </div>

    <!-- Flows table -->
    <div v-else class="overflow-x-auto rounded-lg border border-gray-200">
      <table class="min-w-full divide-y divide-gray-200">
        <thead class="bg-gray-50">
          <tr>
            <th class="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">Source</th>
            <th class="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">Destination</th>
            <th class="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">Direction</th>
            <th class="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">Protocol</th>
            <th class="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">Ports</th>
            <th class="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">Description</th>
            <th class="px-4 py-3 text-right text-xs font-medium uppercase tracking-wider text-gray-500">Actions</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-gray-200 bg-white">
          <FlowRow
            v-for="flow in flows"
            :key="flow.id"
            :flow="flow"
            :actions-disabled="isAddingNew || !!editingFlow"
            :class="{ 'opacity-40': editingFlow && editingFlow.id === flow.id }"
            @edit="startEditing(flow)"
            @delete="confirmDeleteFlow(flow)"
          />

          <!-- Empty state -->
          <tr v-if="flows.length === 0">
            <td colspan="7" class="px-4 py-8 text-center text-sm text-gray-500">
              No flows defined yet. Click "Add Flow" to add one.
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Delete confirmation modal -->
    <ConfirmModal
      :show="showDeleteModal"
      title="Delete Flow"
      :message="`Are you sure you want to delete this flow (${flowToDelete?.source_cidr} → ${flowToDelete?.destination_cidr})?`"
      confirm-text="Delete"
      cancel-text="Cancel"
      @confirm="deleteFlow"
      @cancel="showDeleteModal = false"
    />

    <!-- Toast -->
    <Toast
      :show="toast.show"
      :message="toast.message"
      :type="toast.type"
      @dismiss="toast.show = false"
    />
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useApi } from '../../composables/useApi.js'
import FlowForm from './FlowForm.vue'
import FlowRow from './FlowRow.vue'
import ConfirmModal from '../shared/ConfirmModal.vue'
import Toast from '../shared/Toast.vue'

const props = defineProps({
  requestId: {
    type: [String, Number],
    required: true,
  },
})

// Two instances: the list's loading/error drive the table state; mutations
// (save/delete) must not blank the table out when they fail or run.
const { apiFetch, loading, error } = useApi()
const { apiFetch: mutateFetch } = useApi()

const flows = ref([])
const editingFlow = ref(null)
const isAddingNew = ref(false)
const showDeleteModal = ref(false)
const flowToDelete = ref(null)

const newFlow = ref(createEmptyFlow())

const toast = ref({
  show: false,
  message: '',
  type: 'info',
})

function createEmptyFlow() {
  return {
    source_cidr: '',
    destination_cidr: '',
    direction: 'outbound',
    protocol: 'tcp',
    destination_ports: '',
    description: '',
  }
}

function showToast(message, type = 'success') {
  toast.value = { show: true, message, type }
}

function apiErrorMessage(data, fallback) {
  if (data?.errors) {
    return Object.entries(data.errors)
      .map(([field, msgs]) => `${field}: ${Array.isArray(msgs) ? msgs.join(' ') : msgs}`)
      .join('; ')
  }
  return data?.error || fallback
}

async function loadFlows() {
  const result = await apiFetch(`/api/vpn/requests/${props.requestId}/flows/`)
  if (result.ok) {
    flows.value = result.data.flows || []
  }
}

function addNewFlow() {
  isAddingNew.value = true
  newFlow.value = createEmptyFlow()
  editingFlow.value = null
}

function cancelNewFlow() {
  isAddingNew.value = false
  newFlow.value = createEmptyFlow()
}

async function saveNewFlow(flowData) {
  const result = await mutateFetch(`/api/vpn/requests/${props.requestId}/flows/`, {
    method: 'POST',
    body: JSON.stringify(flowData),
  })
  if (result.ok) {
    flows.value.push(result.data)
    isAddingNew.value = false
    newFlow.value = createEmptyFlow()
    showToast('Flow added successfully')
  } else {
    showToast(apiErrorMessage(result.data, 'Failed to add flow'), 'error')
  }
}

function startEditing(flow) {
  editingFlow.value = { ...flow }
  isAddingNew.value = false
}

async function saveExistingFlow(flowData) {
  const result = await mutateFetch(`/api/vpn/flows/${flowData.id}/`, {
    method: 'PATCH',
    body: JSON.stringify(flowData),
  })
  if (result.ok) {
    const idx = flows.value.findIndex((f) => f.id === flowData.id)
    if (idx !== -1) flows.value[idx] = result.data
    editingFlow.value = null
    showToast('Flow updated successfully')
  } else {
    showToast(apiErrorMessage(result.data, 'Failed to update flow'), 'error')
  }
}

function confirmDeleteFlow(flow) {
  flowToDelete.value = flow
  showDeleteModal.value = true
}

async function deleteFlow() {
  const flow = flowToDelete.value
  showDeleteModal.value = false
  const result = await mutateFetch(`/api/vpn/flows/${flow.id}/`, {
    method: 'DELETE',
  })
  if (result.ok) {
    flows.value = flows.value.filter((f) => f.id !== flow.id)
    if (editingFlow.value && editingFlow.value.id === flow.id) {
      editingFlow.value = null
    }
    showToast('Flow deleted successfully')
  } else {
    showToast(apiErrorMessage(result.data, 'Failed to delete flow'), 'error')
  }
  flowToDelete.value = null
}

onMounted(() => {
  loadFlows()
})
</script>
