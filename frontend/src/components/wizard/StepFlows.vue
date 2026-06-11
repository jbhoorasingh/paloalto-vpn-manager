<template>
  <div class="space-y-6">
    <div>
      <h2 class="text-xl font-semibold text-gray-900">Traffic Flows</h2>
      <p class="mt-1 text-sm text-gray-500">Define the traffic flows that will traverse this VPN tunnel.</p>
    </div>

    <div v-if="requestId">
      <FlowsEditor :request-id="requestId" />
    </div>

    <div v-else class="rounded-md bg-yellow-50 p-4 text-sm text-yellow-700">
      <div class="flex">
        <svg class="mr-2 h-5 w-5 flex-shrink-0 text-yellow-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z" />
        </svg>
        <p>The request must be saved before flows can be added. Please navigate back and forward to trigger a save.</p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { useWizardState } from '../../composables/useWizardState.js'
import FlowsEditor from '../flows/FlowsEditor.vue'

const { requestId } = useWizardState()
</script>
