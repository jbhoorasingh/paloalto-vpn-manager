<template>
  <span
    :class="[
      'inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium',
      badgeClasses,
    ]"
  >
    {{ displayLabel }}
  </span>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  status: {
    type: String,
    required: true,
  },
})

const statusConfig = {
  draft: { bg: 'bg-gray-100', text: 'text-gray-800', label: 'Draft' },
  submitted: { bg: 'bg-blue-100', text: 'text-blue-800', label: 'Submitted' },
  pending_review: { bg: 'bg-blue-100', text: 'text-blue-800', label: 'Pending Review' },
  approved: { bg: 'bg-green-100', text: 'text-green-800', label: 'Approved' },
  security_approved: { bg: 'bg-green-100', text: 'text-green-800', label: 'Security Approved' },
  network_approved: { bg: 'bg-green-100', text: 'text-green-800', label: 'Network Approved' },
  changes_requested: { bg: 'bg-yellow-100', text: 'text-yellow-800', label: 'Changes Requested' },
  vendor_changes_requested: { bg: 'bg-yellow-100', text: 'text-yellow-800', label: 'Vendor Changes' },
  rejected: { bg: 'bg-red-100', text: 'text-red-800', label: 'Rejected' },
  active: { bg: 'bg-green-100', text: 'text-green-800', label: 'Active' },
  provisioning: { bg: 'bg-indigo-100', text: 'text-indigo-800', label: 'Provisioning' },
  decommissioned: { bg: 'bg-red-100', text: 'text-red-800', label: 'Decommissioned' },
  decommission_requested: { bg: 'bg-red-100', text: 'text-red-800', label: 'Decommission Requested' },
}

const resolvedConfig = computed(() => {
  const s = props.status?.toLowerCase() || ''
  if (statusConfig[s]) return statusConfig[s]
  // Fallback pattern matching
  if (s.includes('approved')) return { bg: 'bg-green-100', text: 'text-green-800', label: props.status }
  if (s.includes('changes_requested')) return { bg: 'bg-yellow-100', text: 'text-yellow-800', label: props.status }
  if (s.includes('decommission')) return { bg: 'bg-red-100', text: 'text-red-800', label: props.status }
  return { bg: 'bg-gray-100', text: 'text-gray-700', label: props.status }
})

const badgeClasses = computed(() => `${resolvedConfig.value.bg} ${resolvedConfig.value.text}`)
const displayLabel = computed(() => resolvedConfig.value.label)
</script>
