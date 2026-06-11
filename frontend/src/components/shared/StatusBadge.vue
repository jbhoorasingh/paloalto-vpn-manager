<template>
  <span
    :class="[
      'inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold whitespace-nowrap',
      resolved.classes,
    ]"
  >
    {{ resolved.label }}
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

// Canonical tones — keep in sync with apps/ui/templates/components/status_badge.html
const TONES = {
  slate: 'bg-slate-100 text-slate-700 ring-1 ring-inset ring-slate-300',
  blue: 'bg-blue-50 text-blue-700 ring-1 ring-inset ring-blue-600/20',
  emerald: 'bg-emerald-50 text-emerald-700 ring-1 ring-inset ring-emerald-600/20',
  amber: 'bg-amber-50 text-amber-700 ring-1 ring-inset ring-amber-600/20',
  red: 'bg-red-50 text-red-700 ring-1 ring-inset ring-red-600/20',
  indigo: 'bg-indigo-50 text-indigo-700 ring-1 ring-inset ring-indigo-600/20',
  orange: 'bg-orange-50 text-orange-700 ring-1 ring-inset ring-orange-600/20',
}

// Mirrors apps.vpn.models.request.RequestStatus
const STATUS_CONFIG = {
  draft: { tone: 'slate', label: 'Draft' },
  submitted: { tone: 'blue', label: 'Submitted' },
  infosec_approved: { tone: 'emerald', label: 'InfoSec Approved' },
  infosec_changes_requested: { tone: 'amber', label: 'InfoSec Changes Requested' },
  network_approved: { tone: 'emerald', label: 'Network Approved' },
  network_changes_requested: { tone: 'amber', label: 'Network Changes Requested' },
  rejected: { tone: 'red', label: 'Rejected' },
  scheduled: { tone: 'indigo', label: 'Scheduled' },
  deploy_ready: { tone: 'indigo', label: 'Deploy Ready' },
  deployed: { tone: 'indigo', label: 'Deployed' },
  active: { tone: 'emerald', label: 'Active' },
  recert_due: { tone: 'orange', label: 'Recert Due' },
  recert_in_review: { tone: 'orange', label: 'Recert In Review' },
  recert_approved: { tone: 'emerald', label: 'Recert Approved' },
  decommission_requested: { tone: 'red', label: 'Decommission Requested' },
  decommission_approved: { tone: 'red', label: 'Decommission Approved' },
  decommissioned: { tone: 'slate', label: 'Decommissioned' },
}

const resolved = computed(() => {
  const s = props.status?.toLowerCase() || ''
  const config = STATUS_CONFIG[s]
  if (config) {
    return { classes: TONES[config.tone], label: config.label }
  }
  // Unknown status — show it title-cased rather than raw snake_case
  const label = s.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase()) || props.status
  return { classes: TONES.slate, label }
})
</script>
