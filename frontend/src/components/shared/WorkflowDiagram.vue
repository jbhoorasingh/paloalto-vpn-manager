<template>
  <div class="bg-white rounded-xl border border-slate-200 shadow-sm px-6 py-5 overflow-x-auto">
    <!-- Horizontal stepper -->
    <div class="flex items-center justify-between min-w-[640px]">
      <template v-for="(stage, idx) in stages" :key="stage.key">
        <!-- Stage node -->
        <div class="flex flex-col items-center relative" :style="{ minWidth: '72px' }">
          <!-- Circle -->
          <div
            class="relative flex items-center justify-center w-9 h-9 rounded-full border-2 transition-all"
            :class="circleClass(idx)"
          >
            <!-- Checkmark for completed -->
            <svg v-if="stageState(idx) === 'completed'" class="w-4 h-4 text-white" fill="none" viewBox="0 0 24 24" stroke-width="3" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7" />
            </svg>
            <!-- Dot for current -->
            <span v-else-if="stageState(idx) === 'current'" class="w-2.5 h-2.5 rounded-full bg-indigo-600 animate-pulse" />
            <!-- Number for future -->
            <span v-else class="text-xs font-semibold text-slate-400">{{ idx + 1 }}</span>
          </div>

          <!-- Label -->
          <span
            class="mt-2 text-xs font-medium text-center leading-tight"
            :class="labelClass(idx)"
          >
            {{ stage.label }}
          </span>

          <!-- Side branch indicator (below the label) -->
          <div v-if="branchFor(idx)" class="mt-1.5 flex flex-col items-center">
            <div class="w-px h-3" :class="branchFor(idx).lineClass" />
            <span
              class="mt-0.5 inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-semibold ring-1 ring-inset"
              :class="branchFor(idx).badgeClass"
            >
              {{ branchFor(idx).label }}
            </span>
          </div>
        </div>

        <!-- Connector line between stages -->
        <div
          v-if="idx < stages.length - 1"
          class="flex-1 h-0.5 mx-1 self-start mt-[18px]"
          :class="connectorClass(idx)"
        />
      </template>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  currentStatus: {
    type: String,
    default: 'draft',
  },
})

const stages = [
  { key: 'draft', label: 'Draft' },
  { key: 'submitted', label: 'Submitted' },
  { key: 'infosec_approved', label: 'InfoSec Review' },
  { key: 'network_approved', label: 'Network Review' },
  { key: 'scheduled', label: 'Scheduled' },
  { key: 'deploy_ready', label: 'Deploy Ready' },
  { key: 'deployed', label: 'Deployed' },
  { key: 'active', label: 'Active' },
]

// Map every possible status to the main-stage index it corresponds to
const STATUS_INDEX = {
  draft: 0,
  submitted: 1,
  infosec_changes_requested: 1,
  infosec_approved: 3,       // InfoSec done → now at Network Review
  network_changes_requested: 3,
  network_approved: 4,       // Network done → now at Scheduled
  rejected: 1,
  scheduled: 4,
  deploy_ready: 5,
  deployed: 6,
  active: 7,
}

const BRANCH_STATUSES = new Set([
  'infosec_changes_requested',
  'network_changes_requested',
  'rejected',
])

const currentIndex = computed(() => {
  const idx = STATUS_INDEX[props.currentStatus]
  return idx !== undefined ? idx : 0
})

const isBranchStatus = computed(() => BRANCH_STATUSES.has(props.currentStatus))

function stageState(idx) {
  if (idx < currentIndex.value) return 'completed'
  if (idx === currentIndex.value) {
    // If on a branch status, the "current" main node shows as the last completed/waiting node
    if (isBranchStatus.value) return 'completed'
    return 'current'
  }
  return 'future'
}

function circleClass(idx) {
  const state = stageState(idx)
  if (state === 'completed') return 'bg-emerald-500 border-emerald-500 text-white'
  if (state === 'current') return 'border-indigo-600 bg-white'
  return 'border-slate-300 bg-white'
}

function labelClass(idx) {
  const state = stageState(idx)
  if (state === 'completed') return 'text-emerald-700'
  if (state === 'current') return 'text-indigo-700 font-semibold'
  return 'text-slate-400'
}

function connectorClass(idx) {
  if (idx < currentIndex.value) return 'bg-emerald-500'
  return 'bg-slate-200'
}

// Returns branch info for a stage index, or null
function branchFor(idx) {
  if (!isBranchStatus.value) return null

  if (props.currentStatus === 'infosec_changes_requested' && idx === 1) {
    return {
      label: 'Changes Requested',
      lineClass: 'bg-amber-400',
      badgeClass: 'bg-amber-50 text-amber-700 ring-amber-600/20',
    }
  }
  if (props.currentStatus === 'network_changes_requested' && idx === 3) {
    return {
      label: 'Changes Requested',
      lineClass: 'bg-amber-400',
      badgeClass: 'bg-amber-50 text-amber-700 ring-amber-600/20',
    }
  }
  if (props.currentStatus === 'rejected' && idx === 1) {
    return {
      label: 'Rejected',
      lineClass: 'bg-red-400',
      badgeClass: 'bg-red-50 text-red-700 ring-red-600/20',
    }
  }
  return null
}
</script>
