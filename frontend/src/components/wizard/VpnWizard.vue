<template>
  <div class="mx-auto max-w-4xl px-4 py-8">
    <!-- Loading initial data -->
    <div v-if="initialLoading" class="flex items-center justify-center py-20">
      <svg class="mr-3 h-6 w-6 animate-spin text-indigo-600" fill="none" viewBox="0 0 24 24">
        <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
        <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
      </svg>
      <span class="text-gray-600">Loading wizard...</span>
    </div>

    <!-- Initialization error -->
    <div v-else-if="initError" class="rounded-md bg-red-50 p-6 text-center">
      <svg class="mx-auto h-10 w-10 text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z" />
      </svg>
      <h3 class="mt-3 text-lg font-medium text-red-800">Failed to load wizard</h3>
      <p class="mt-1 text-sm text-red-600">{{ initError }}</p>
      <button
        type="button"
        class="mt-4 rounded-md bg-red-100 px-4 py-2 text-sm font-medium text-red-800 hover:bg-red-200"
        @click="initialize"
      >
        Retry
      </button>
    </div>

    <!-- Wizard content -->
    <template v-else>
      <!-- Reviewer comments banner (for changes-requested resubmission) -->
      <div v-if="isResubmission" class="mb-6 rounded-lg border border-amber-300 bg-amber-50 p-4">
        <div class="flex items-start gap-3">
          <svg class="mt-0.5 h-5 w-5 flex-shrink-0 text-amber-600" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z" />
          </svg>
          <div>
            <h3 class="text-sm font-semibold text-amber-800">
              Changes Requested — {{ reviewStage }} Review
            </h3>
            <p v-if="reviewerName" class="mt-0.5 text-xs text-amber-700">
              Reviewer: {{ reviewerName }}
            </p>
            <p v-if="reviewerComments" class="mt-2 text-sm text-amber-900 bg-amber-100/60 rounded px-3 py-2">
              {{ reviewerComments }}
            </p>
          </div>
        </div>
      </div>

      <!-- Header -->
      <div class="mb-8">
        <h1 class="text-2xl font-bold text-gray-900">
          {{ isResubmission ? 'Edit & Resubmit VPN Request' : requestId ? 'Edit VPN Request' : 'New VPN Request' }}
        </h1>
        <p v-if="requestId" class="mt-1 text-sm text-gray-500">
          {{ isResubmission ? 'Request' : 'Draft' }} #{{ requestId }}
        </p>
      </div>

      <!-- Stepper progress bar -->
      <nav class="mb-8" aria-label="Progress">
        <ol class="flex items-center">
          <li
            v-for="(step, idx) in STEPS"
            :key="step.id"
            class="relative"
            :class="idx < STEPS.length - 1 ? 'flex-1' : ''"
          >
            <div class="flex items-center">
              <!-- Step circle -->
              <button
                type="button"
                class="relative flex h-8 w-8 items-center justify-center rounded-full text-xs font-semibold transition-colors"
                :class="stepCircleClass(step.id)"
                @click="handleStepClick(step.id)"
              >
                <!-- Completed check -->
                <svg
                  v-if="step.id < currentStep"
                  class="h-4 w-4 text-white"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="3" d="M5 13l4 4L19 7" />
                </svg>
                <span v-else>{{ step.id }}</span>
              </button>

              <!-- Connector line -->
              <div
                v-if="idx < STEPS.length - 1"
                class="ml-1 mr-1 h-0.5 flex-1 transition-colors"
                :class="step.id < currentStep ? 'bg-indigo-600' : 'bg-gray-200'"
              />
            </div>

            <!-- Step label -->
            <span
              class="absolute -bottom-6 left-0 w-max text-xs font-medium"
              :class="step.id === currentStep ? 'text-indigo-600' : step.id < currentStep ? 'text-gray-600' : 'text-gray-400'"
            >
              {{ step.name }}
            </span>
          </li>
        </ol>
      </nav>

      <!-- Spacer for step labels -->
      <div class="mb-4" />

      <!-- Save indicator -->
      <div v-if="saving" class="mb-4 flex items-center gap-2 text-sm text-gray-500">
        <svg class="h-4 w-4 animate-spin" fill="none" viewBox="0 0 24 24">
          <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
          <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
        </svg>
        Saving...
      </div>

      <!-- Error display -->
      <div v-if="saveError" class="mb-4 rounded-md bg-red-50 border border-red-200 p-3 text-sm text-red-700">
        {{ saveError }}
      </div>

      <!-- Step content area -->
      <div class="min-h-[400px] rounded-lg border border-gray-200 bg-white p-6 shadow-sm">
        <StepVendor v-if="currentStep === 1" />
        <StepAppsData v-else-if="currentStep === 2" :applications="applications" />
        <StepTopology v-else-if="currentStep === 3" :sites="sites" />
        <StepCrypto v-else-if="currentStep === 4" />
        <StepRouting v-else-if="currentStep === 5" :sites="sites" />
        <StepFlows v-else-if="currentStep === 6" />
        <StepReview v-else-if="currentStep === 7" :sites="sites" :applications="applications" />
      </div>

      <!-- Navigation buttons -->
      <div class="mt-6 flex items-center justify-between">
        <button
          v-if="!isFirstStep"
          type="button"
          class="inline-flex items-center rounded-md border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 shadow-sm hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2"
          @click="handleBack"
        >
          <svg class="mr-2 h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7" />
          </svg>
          Back
        </button>
        <div v-else />

        <div class="flex gap-3">
          <!-- Save Draft button (visible on all steps except review) -->
          <button
            v-if="!isLastStep"
            type="button"
            class="inline-flex items-center rounded-md border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 shadow-sm hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2"
            :disabled="saving"
            @click="saveDraft"
          >
            Save Draft
          </button>

          <!-- Next / Submit button -->
          <button
            v-if="!isLastStep"
            type="button"
            class="inline-flex items-center rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2"
            :disabled="saving"
            @click="handleNext"
          >
            Next
            <svg class="ml-2 h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" />
            </svg>
          </button>

          <button
            v-else
            type="button"
            class="inline-flex items-center rounded-md bg-green-600 px-6 py-2 text-sm font-medium text-white shadow-sm hover:bg-green-700 focus:outline-none focus:ring-2 focus:ring-green-500 focus:ring-offset-2"
            :disabled="submitting"
            @click="handleSubmit"
          >
            <svg v-if="submitting" class="mr-2 h-4 w-4 animate-spin" fill="none" viewBox="0 0 24 24">
              <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
              <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
            {{ submitting ? 'Submitting...' : isResubmission ? 'Resubmit Request' : 'Submit Request' }}
          </button>
        </div>
      </div>
    </template>

    <!-- Toast notifications -->
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
import { createWizardState } from '../../composables/useWizardState.js'
import { useApi } from '../../composables/useApi.js'
import StepVendor from './StepVendor.vue'
import StepAppsData from './StepAppsData.vue'
import StepTopology from './StepTopology.vue'
import StepCrypto from './StepCrypto.vue'
import StepRouting from './StepRouting.vue'
import StepFlows from './StepFlows.vue'
import StepReview from './StepReview.vue'
import Toast from '../shared/Toast.vue'

const props = defineProps({
  id: {
    type: [String, Number],
    default: null,
  },
  sites: {
    type: Array,
    default: () => [],
  },
  applications: {
    type: Array,
    default: () => [],
  },
})

const { apiFetch } = useApi()

const initialLoading = ref(true)
const initError = ref(null)
const saveError = ref(null)
const submitting = ref(false)

const reviewerComments = ref('')
const reviewerName = ref('')
const reviewStage = ref('')
const isResubmission = ref(false)

const toast = ref({
  show: false,
  message: '',
  type: 'info',
})

// Initialize wizard state (will be populated after loading)
const {
  STEPS,
  currentStep,
  requestId,
  saving,
  errors,
  formData,
  isFirstStep,
  isLastStep,
  nextStep,
  prevStep,
  goToStep,
} = createWizardState({})

function showToast(message, type = 'success') {
  toast.value = { show: true, message, type }
}

function stepCircleClass(stepId) {
  if (stepId < currentStep.value) return 'bg-indigo-600 text-white cursor-pointer hover:bg-indigo-700'
  if (stepId === currentStep.value) return 'border-2 border-indigo-600 bg-white text-indigo-600'
  return 'border-2 border-gray-300 bg-white text-gray-400'
}

async function handleStepClick(stepId) {
  if (stepId < currentStep.value) {
    await autoSaveCurrentStep()
    goToStep(stepId)
  }
}

async function initialize() {
  initialLoading.value = true
  initError.value = null

  try {
    if (props.id) {
      // Load existing draft
      const result = await apiFetch(`/api/vpn/wizard/${props.id}/`)
      if (result.ok) {
        Object.assign(formData, result.data)
        requestId.value = props.id
        // Capture reviewer comments for changes-requested resubmission
        if (result.data.reviewer_comments !== undefined) {
          reviewerComments.value = result.data.reviewer_comments || ''
          reviewerName.value = result.data.reviewer_name || ''
          reviewStage.value = result.data.review_stage || ''
          isResubmission.value = true
        }
      } else {
        initError.value = result.data?.error || 'Failed to load draft'
        return
      }
    }
    // New request: don't create draft yet — wait until user saves or clicks Next
  } catch (err) {
    initError.value = err.message
  } finally {
    initialLoading.value = false
  }
}

async function createDraft() {
  const result = await apiFetch('/api/vpn/wizard/create/', { method: 'POST' })
  if (result.ok) {
    requestId.value = result.data.id
    return true
  } else {
    saveError.value = result.data?.error || 'Failed to create draft'
    return false
  }
}

async function autoSaveCurrentStep() {
  saving.value = true
  saveError.value = null

  // Create draft on first save if it doesn't exist yet
  if (!requestId.value) {
    const created = await createDraft()
    if (!created) {
      saving.value = false
      return false
    }
  }

  const result = await apiFetch(
    `/api/vpn/wizard/${requestId.value}/step/${currentStep.value}/`,
    {
      method: 'PATCH',
      body: JSON.stringify(formData),
    }
  )

  saving.value = false

  if (!result.ok) {
    saveError.value = result.data?.error || 'Failed to save step'
    if (result.data?.field_errors) {
      Object.assign(errors.value, result.data.field_errors)
    } else if (result.data?.errors) {
      Object.assign(errors.value, result.data.errors)
    }
    return false
  }

  errors.value = {}
  return true
}

async function saveDraft() {
  const success = await autoSaveCurrentStep()
  if (success) {
    showToast('Draft saved successfully')
  }
}

async function handleNext() {
  const success = await autoSaveCurrentStep()
  if (success !== false) {
    nextStep()
  }
}

async function handleBack() {
  await autoSaveCurrentStep()
  prevStep()
}

async function handleSubmit() {
  submitting.value = true
  saveError.value = null

  // First save the current step
  await autoSaveCurrentStep()

  // Then submit
  const result = await apiFetch(`/api/vpn/wizard/${requestId.value}/submit/`, {
    method: 'POST',
  })

  submitting.value = false

  if (result.ok) {
    showToast('Request submitted successfully!', 'success')
    // Redirect to request detail or dashboard
    setTimeout(() => {
      window.location.href = result.data.redirect_url || `/vpn/requests/${requestId.value}/`
    }, 1500)
  } else {
    if (result.data?.errors) {
      Object.assign(errors.value, result.data.errors)
    }
    saveError.value = result.data?.error || 'Submission failed. Please review the errors above.'
    showToast('Submission failed. Please fix the errors.', 'error')
  }
}

onMounted(() => {
  initialize()
})
</script>
