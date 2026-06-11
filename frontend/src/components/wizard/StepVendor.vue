<template>
  <div class="space-y-6">
    <div>
      <h2 class="text-xl font-semibold text-gray-900">Vendor Selection</h2>
      <p class="mt-1 text-sm text-gray-500">Search for an existing vendor or create a new one.</p>
    </div>

    <!-- Vendor search -->
    <div v-if="!showCreateForm">
      <label class="block text-sm font-medium text-gray-700">Search Vendor</label>
      <div class="relative mt-1">
        <input
          v-model="searchQuery"
          type="text"
          placeholder="Type to search vendors..."
          class="block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
          @input="debouncedSearch"
          @focus="showResults = true"
        />
        <div v-if="searching" class="pointer-events-none absolute inset-y-0 right-0 flex items-center pr-3">
          <svg class="h-4 w-4 animate-spin text-gray-400" fill="none" viewBox="0 0 24 24">
            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
          </svg>
        </div>

        <!-- Search results dropdown -->
        <div
          v-if="showResults && searchResults.length > 0"
          class="absolute z-10 mt-1 max-h-60 w-full overflow-auto rounded-md border border-gray-200 bg-white shadow-lg"
        >
          <button
            v-for="vendor in searchResults"
            :key="vendor.id"
            type="button"
            class="flex w-full items-center px-4 py-3 text-left text-sm hover:bg-indigo-50"
            @click="selectVendor(vendor)"
          >
            <div>
              <div class="font-medium text-gray-900">{{ vendor.name }}</div>
              <div class="text-xs text-gray-500">{{ vendor.domain }}</div>
            </div>
          </button>
        </div>

        <!-- No results -->
        <div
          v-if="showResults && searchQuery.length >= 2 && searchResults.length === 0 && !searching"
          class="absolute z-10 mt-1 w-full rounded-md border border-gray-200 bg-white p-4 text-sm text-gray-500 shadow-lg"
        >
          No vendors found matching "{{ searchQuery }}"
        </div>
      </div>

      <!-- Selected vendor display -->
      <div v-if="formData.vendor_id" class="mt-4 rounded-lg border border-green-200 bg-green-50 p-4">
        <div class="flex items-center justify-between">
          <div>
            <h4 class="font-medium text-green-900">{{ formData.vendor_name }}</h4>
            <p v-if="selectedVendorDetails.domain" class="text-sm text-green-700">
              {{ selectedVendorDetails.domain }}
            </p>
            <p v-if="selectedVendorDetails.support_email" class="text-sm text-green-700">
              {{ selectedVendorDetails.support_email }}
            </p>
          </div>
          <button
            type="button"
            class="text-sm text-green-700 underline hover:text-green-900"
            @click="clearVendor"
          >
            Change
          </button>
        </div>
      </div>

      <!-- Create new vendor link -->
      <div class="mt-4">
        <button
          type="button"
          class="text-sm font-medium text-indigo-600 hover:text-indigo-500"
          @click="showCreateForm = true"
        >
          + Create New Vendor
        </button>
      </div>
    </div>

    <!-- Create new vendor inline form -->
    <div v-if="showCreateForm" class="rounded-lg border border-gray-200 bg-gray-50 p-6">
      <div class="mb-4 flex items-center justify-between">
        <h3 class="text-lg font-medium text-gray-900">Create New Vendor</h3>
        <button
          type="button"
          class="text-sm text-gray-500 hover:text-gray-700"
          @click="showCreateForm = false"
        >
          Cancel
        </button>
      </div>

      <div class="space-y-4">
        <div>
          <label class="block text-sm font-medium text-gray-700">Vendor Name *</label>
          <input
            v-model="newVendor.name"
            type="text"
            required
            class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
            placeholder="e.g., Acme Corp"
          />
        </div>
        <div>
          <label class="block text-sm font-medium text-gray-700">Domain</label>
          <input
            v-model="newVendor.domain"
            type="text"
            class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
            placeholder="e.g., acmecorp.com"
          />
        </div>
        <div>
          <label class="block text-sm font-medium text-gray-700">Support Email</label>
          <input
            v-model="newVendor.support_email"
            type="email"
            class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
            placeholder="e.g., support@acmecorp.com"
          />
        </div>

        <div v-if="createError" class="rounded-md bg-red-50 p-3 text-sm text-red-700">
          {{ createError }}
        </div>

        <button
          type="button"
          class="inline-flex items-center rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2"
          :disabled="creatingVendor || !newVendor.name.trim()"
          @click="createVendor"
        >
          <svg v-if="creatingVendor" class="mr-2 h-4 w-4 animate-spin" fill="none" viewBox="0 0 24 24">
            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
          </svg>
          {{ creatingVendor ? 'Creating...' : 'Create Vendor' }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { useWizardState } from '../../composables/useWizardState.js'
import { useApi } from '../../composables/useApi.js'

const { formData } = useWizardState()
const { apiFetch } = useApi()

const searchQuery = ref(formData.vendor_name || '')
const searchResults = ref([])
const showResults = ref(false)
const searching = ref(false)
const showCreateForm = ref(false)
const selectedVendorDetails = reactive({ domain: '', support_email: '' })

const newVendor = reactive({
  name: '',
  domain: '',
  support_email: '',
})
const creatingVendor = ref(false)
const createError = ref('')

let searchTimeout = null

function debouncedSearch() {
  clearTimeout(searchTimeout)
  showResults.value = true
  if (searchQuery.value.length < 2) {
    searchResults.value = []
    return
  }
  searchTimeout = setTimeout(searchVendors, 300)
}

async function searchVendors() {
  searching.value = true
  const result = await apiFetch(`/api/vpn/vendors/?q=${encodeURIComponent(searchQuery.value)}`)
  searching.value = false
  if (result.ok) {
    searchResults.value = result.data.vendors || result.data.results || []
  }
}

function selectVendor(vendor) {
  formData.vendor_id = vendor.id
  formData.vendor_name = vendor.name
  searchQuery.value = vendor.name
  selectedVendorDetails.domain = vendor.domain || ''
  selectedVendorDetails.support_email = vendor.support_email || ''
  showResults.value = false
  searchResults.value = []
}

function clearVendor() {
  formData.vendor_id = null
  formData.vendor_name = ''
  searchQuery.value = ''
  selectedVendorDetails.domain = ''
  selectedVendorDetails.support_email = ''
}

async function createVendor() {
  creatingVendor.value = true
  createError.value = ''
  const result = await apiFetch('/api/vpn/vendors/create/', {
    method: 'POST',
    body: JSON.stringify({
      name: newVendor.name.trim(),
      domain: newVendor.domain.trim(),
      support_email: newVendor.support_email.trim(),
    }),
  })
  creatingVendor.value = false

  if (result.ok) {
    selectVendor(result.data)
    showCreateForm.value = false
    newVendor.name = ''
    newVendor.domain = ''
    newVendor.support_email = ''
  } else {
    createError.value = result.data?.error || result.data?.name?.[0] || 'Failed to create vendor'
  }
}

// Close dropdown on click outside
onMounted(() => {
  document.addEventListener('click', (e) => {
    if (!e.target.closest('.relative')) {
      showResults.value = false
    }
  })
})
</script>
