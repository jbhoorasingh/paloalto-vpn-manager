<template>
  <div class="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-6">
    <div
      v-for="stat in statItems"
      :key="stat.key"
      class="rounded-lg border p-4 shadow-sm"
      :class="stat.borderColor"
    >
      <div class="flex items-center justify-between">
        <p class="text-sm font-medium" :class="stat.labelColor">
          {{ stat.label }}
        </p>
        <div
          class="flex h-8 w-8 items-center justify-center rounded-full"
          :class="stat.iconBg"
        >
          <component :is="stat.icon" class="h-4 w-4" :class="stat.iconColor" />
        </div>
      </div>
      <p class="mt-2 text-2xl font-bold" :class="stat.valueColor">
        {{ stat.count }}
      </p>
    </div>
  </div>
</template>

<script setup>
import { computed, h } from 'vue'

const props = defineProps({
  stats: {
    type: Object,
    default: () => ({}),
  },
})

// Simple SVG icon components
const DocumentIcon = {
  render() {
    return h('svg', { fill: 'none', stroke: 'currentColor', viewBox: '0 0 24 24' }, [
      h('path', {
        'stroke-linecap': 'round',
        'stroke-linejoin': 'round',
        'stroke-width': '2',
        d: 'M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z',
      }),
    ])
  },
}

const PencilIcon = {
  render() {
    return h('svg', { fill: 'none', stroke: 'currentColor', viewBox: '0 0 24 24' }, [
      h('path', {
        'stroke-linecap': 'round',
        'stroke-linejoin': 'round',
        'stroke-width': '2',
        d: 'M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z',
      }),
    ])
  },
}

const PaperAirplaneIcon = {
  render() {
    return h('svg', { fill: 'none', stroke: 'currentColor', viewBox: '0 0 24 24' }, [
      h('path', {
        'stroke-linecap': 'round',
        'stroke-linejoin': 'round',
        'stroke-width': '2',
        d: 'M12 19l9 2-9-18-9 18 9-2zm0 0v-8',
      }),
    ])
  },
}

const CheckCircleIcon = {
  render() {
    return h('svg', { fill: 'none', stroke: 'currentColor', viewBox: '0 0 24 24' }, [
      h('path', {
        'stroke-linecap': 'round',
        'stroke-linejoin': 'round',
        'stroke-width': '2',
        d: 'M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z',
      }),
    ])
  },
}

const BoltIcon = {
  render() {
    return h('svg', { fill: 'none', stroke: 'currentColor', viewBox: '0 0 24 24' }, [
      h('path', {
        'stroke-linecap': 'round',
        'stroke-linejoin': 'round',
        'stroke-width': '2',
        d: 'M13 10V3L4 14h7v7l9-11h-7z',
      }),
    ])
  },
}

const ExclamationIcon = {
  render() {
    return h('svg', { fill: 'none', stroke: 'currentColor', viewBox: '0 0 24 24' }, [
      h('path', {
        'stroke-linecap': 'round',
        'stroke-linejoin': 'round',
        'stroke-width': '2',
        d: 'M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z',
      }),
    ])
  },
}

const statDefinitions = [
  {
    key: 'total',
    label: 'Total',
    borderColor: 'border-gray-200 bg-white',
    labelColor: 'text-gray-600',
    valueColor: 'text-gray-900',
    iconBg: 'bg-gray-100',
    iconColor: 'text-gray-500',
    icon: DocumentIcon,
  },
  {
    key: 'draft',
    label: 'Drafts',
    borderColor: 'border-gray-200 bg-white',
    labelColor: 'text-gray-600',
    valueColor: 'text-gray-700',
    iconBg: 'bg-gray-100',
    iconColor: 'text-gray-500',
    icon: PencilIcon,
  },
  {
    key: 'submitted',
    label: 'Submitted',
    borderColor: 'border-blue-200 bg-blue-50',
    labelColor: 'text-blue-700',
    valueColor: 'text-blue-900',
    iconBg: 'bg-blue-100',
    iconColor: 'text-blue-600',
    icon: PaperAirplaneIcon,
  },
  {
    key: 'approved',
    label: 'Approved',
    borderColor: 'border-green-200 bg-green-50',
    labelColor: 'text-green-700',
    valueColor: 'text-green-900',
    iconBg: 'bg-green-100',
    iconColor: 'text-green-600',
    icon: CheckCircleIcon,
  },
  {
    key: 'active',
    label: 'Active',
    borderColor: 'border-emerald-200 bg-emerald-50',
    labelColor: 'text-emerald-700',
    valueColor: 'text-emerald-900',
    iconBg: 'bg-emerald-100',
    iconColor: 'text-emerald-600',
    icon: BoltIcon,
  },
  {
    key: 'changes_requested',
    label: 'Changes Req.',
    borderColor: 'border-yellow-200 bg-yellow-50',
    labelColor: 'text-yellow-700',
    valueColor: 'text-yellow-900',
    iconBg: 'bg-yellow-100',
    iconColor: 'text-yellow-600',
    icon: ExclamationIcon,
  },
]

const statItems = computed(() => {
  return statDefinitions
    .filter((def) => props.stats[def.key] !== undefined)
    .map((def) => ({
      ...def,
      count: props.stats[def.key] ?? 0,
    }))
})
</script>
