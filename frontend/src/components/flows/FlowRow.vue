<template>
  <tr class="hover:bg-gray-50">
    <td class="whitespace-nowrap px-4 py-3 text-sm font-mono text-gray-900">
      {{ flow.source_cidr }}
    </td>
    <td class="whitespace-nowrap px-4 py-3 text-sm font-mono text-gray-900">
      {{ flow.destination_cidr }}
    </td>
    <td class="whitespace-nowrap px-4 py-3 text-sm">
      <span
        v-if="flow.direction === 'inbound'"
        class="inline-flex items-center gap-1 rounded-full bg-emerald-50 px-2.5 py-0.5 text-xs font-medium text-emerald-700"
      >
        <svg class="h-3 w-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 17l-5-5m0 0l5-5m-5 5h12" />
        </svg>
        Inbound
      </span>
      <span
        v-else
        class="inline-flex items-center gap-1 rounded-full bg-blue-50 px-2.5 py-0.5 text-xs font-medium text-blue-700"
      >
        Outbound
        <svg class="h-3 w-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 7l5 5m0 0l-5 5m5-5H6" />
        </svg>
      </span>
    </td>
    <td class="whitespace-nowrap px-4 py-3 text-sm text-gray-900">
      {{ protocolLabel }}
    </td>
    <td class="whitespace-nowrap px-4 py-3 text-sm font-mono text-gray-900">
      {{ flow.destination_ports || 'any' }}
    </td>
    <td class="px-4 py-3 text-sm text-gray-600">
      {{ flow.description }}
    </td>
    <td class="whitespace-nowrap px-4 py-3 text-right text-sm">
      <button
        type="button"
        class="mr-2 text-indigo-600 hover:text-indigo-900 disabled:cursor-not-allowed disabled:text-gray-300"
        :disabled="actionsDisabled"
        @click="$emit('edit')"
      >
        Edit
      </button>
      <button
        type="button"
        class="text-red-600 hover:text-red-900 disabled:cursor-not-allowed disabled:text-gray-300"
        :disabled="actionsDisabled"
        @click="$emit('delete')"
      >
        Delete
      </button>
    </td>
  </tr>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  flow: {
    type: Object,
    required: true,
  },
  actionsDisabled: {
    type: Boolean,
    default: false,
  },
})

defineEmits(['edit', 'delete'])

const protocolLabel = computed(() => {
  const protos = Array.isArray(props.flow.protocols)
    ? props.flow.protocols
    : (props.flow.protocols || props.flow.protocol || '')
        .toString()
        .split(',')
        .filter(Boolean)
  return protos.map((p) => p.toUpperCase()).join(', ')
})
</script>
