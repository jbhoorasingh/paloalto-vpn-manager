<template>
  <div class="space-y-6">
    <div>
      <h2 class="text-xl font-semibold text-gray-900">Applications & Data</h2>
      <p class="mt-1 text-sm text-gray-500">Describe the applications and data involved in this VPN connection.</p>
    </div>

    <!-- Title -->
    <div>
      <label for="title" class="block text-sm font-medium text-gray-700">
        Request Title <span class="text-red-500">*</span>
      </label>
      <input
        id="title"
        v-model="formData.title"
        type="text"
        required
        class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
        placeholder="e.g., Acme Corp Data Sync VPN"
      />
      <p v-if="errors.title" class="mt-1 text-sm text-red-600">{{ errors.title }}</p>
    </div>

    <!-- Purpose -->
    <div>
      <label for="purpose" class="block text-sm font-medium text-gray-700">Purpose</label>
      <textarea
        id="purpose"
        v-model="formData.purpose"
        rows="3"
        class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
        placeholder="Describe the business purpose of this VPN connection..."
      />
    </div>

    <!-- Applications multi-select -->
    <div>
      <label class="block text-sm font-medium text-gray-700">Applications</label>
      <p class="mb-2 text-xs text-gray-500">Select all applications that will use this VPN.</p>
      <div class="mt-1 max-h-48 overflow-y-auto rounded-md border border-gray-300 bg-white">
        <label
          v-for="app in applications"
          :key="app.id"
          class="flex cursor-pointer items-center px-4 py-2 hover:bg-gray-50"
        >
          <input
            type="checkbox"
            :value="app.id"
            v-model="formData.application_ids"
            class="h-4 w-4 rounded border-gray-300 text-indigo-600 focus:ring-indigo-500"
          />
          <span class="ml-3 text-sm text-gray-700">{{ app.name }}</span>
        </label>
        <div v-if="!applications.length" class="px-4 py-3 text-sm text-gray-500">
          No applications available.
        </div>
      </div>
      <p class="mt-1 text-xs text-gray-500">
        {{ formData.application_ids.length }} application(s) selected
      </p>
    </div>

    <!-- Directionality -->
    <div>
      <label for="directionality" class="block text-sm font-medium text-gray-700">
        Directionality <span class="text-red-500">*</span>
      </label>
      <select
        id="directionality"
        v-model="formData.directionality"
        class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
      >
        <option value="">Select directionality...</option>
        <option value="we_initiate">We Initiate</option>
        <option value="vendor_initiates">Vendor Initiates</option>
        <option value="both">Both Can Initiate</option>
      </select>
      <p v-if="errors.directionality" class="mt-1 text-sm text-red-600">{{ errors.directionality }}</p>
    </div>

    <!-- Data Description -->
    <div>
      <label for="data_description" class="block text-sm font-medium text-gray-700">Data Description</label>
      <textarea
        id="data_description"
        v-model="formData.data_description"
        rows="3"
        class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
        placeholder="Describe the type of data being transferred..."
      />
    </div>

    <!-- Data Classification -->
    <div>
      <label for="data_classification" class="block text-sm font-medium text-gray-700">
        Data Classification <span class="text-red-500">*</span>
      </label>
      <select
        id="data_classification"
        v-model="formData.data_classification"
        class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
      >
        <option value="">Select classification...</option>
        <option value="public">Public</option>
        <option value="internal">Internal</option>
        <option value="confidential">Confidential</option>
        <option value="restricted">Restricted</option>
      </select>
      <p v-if="errors.data_classification" class="mt-1 text-sm text-red-600">{{ errors.data_classification }}</p>

      <!-- Classification info -->
      <div v-if="formData.data_classification === 'restricted'" class="mt-2 rounded-md bg-red-50 p-3 text-sm text-red-700">
        Restricted data requires additional security review and may impact the crypto requirements.
      </div>
      <div v-else-if="formData.data_classification === 'confidential'" class="mt-2 rounded-md bg-yellow-50 p-3 text-sm text-yellow-700">
        Confidential data requires enhanced encryption settings.
      </div>
    </div>
  </div>
</template>

<script setup>
import { useWizardState } from '../../composables/useWizardState.js'

const props = defineProps({
  applications: {
    type: Array,
    default: () => [],
  },
})

const { formData, errors } = useWizardState()
</script>
