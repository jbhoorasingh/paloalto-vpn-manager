<template>
  <div class="rounded-lg border border-indigo-200 bg-indigo-50/40 p-5">
    <h4 class="text-sm font-semibold text-gray-900">
      {{ isNew ? 'New Traffic Flow' : 'Edit Traffic Flow' }}
    </h4>

    <div class="mt-4 space-y-4">
      <!-- Direction: segmented control -->
      <div>
        <label class="mb-1.5 block text-sm font-medium text-gray-700">Direction</label>
        <div class="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <button
            type="button"
            class="flex items-center gap-3 rounded-lg border px-4 py-3 text-left transition-colors"
            :class="localFlow.direction === 'outbound'
              ? 'border-indigo-600 bg-white ring-1 ring-indigo-600'
              : 'border-gray-300 bg-white hover:border-gray-400'"
            @click="localFlow.direction = 'outbound'"
          >
            <span
              class="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full"
              :class="localFlow.direction === 'outbound' ? 'bg-indigo-600 text-white' : 'bg-gray-100 text-gray-500'"
            >
              <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 7l5 5m0 0l-5 5m5-5H6" />
              </svg>
            </span>
            <span>
              <span class="block text-sm font-semibold text-gray-900">Outbound</span>
              <span class="block text-xs text-gray-500">We initiate &middot; our network &rarr; vendor</span>
            </span>
          </button>
          <button
            type="button"
            class="flex items-center gap-3 rounded-lg border px-4 py-3 text-left transition-colors"
            :class="localFlow.direction === 'inbound'
              ? 'border-indigo-600 bg-white ring-1 ring-indigo-600'
              : 'border-gray-300 bg-white hover:border-gray-400'"
            @click="localFlow.direction = 'inbound'"
          >
            <span
              class="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full"
              :class="localFlow.direction === 'inbound' ? 'bg-indigo-600 text-white' : 'bg-gray-100 text-gray-500'"
            >
              <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 17l-5-5m0 0l5-5m-5 5h12" />
              </svg>
            </span>
            <span>
              <span class="block text-sm font-semibold text-gray-900">Inbound</span>
              <span class="block text-xs text-gray-500">Vendor initiates &middot; vendor &rarr; our network</span>
            </span>
          </button>
        </div>
        <p class="mt-1.5 text-xs text-gray-500">
          Who opens the connection — this decides which boundary NAT pool the flow is translated from.
        </p>
      </div>

      <!-- CIDRs -->
      <div class="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <div>
          <label class="mb-1.5 block text-sm font-medium text-gray-700">
            Source CIDR
            <span class="font-normal text-gray-400">
              {{ localFlow.direction === 'inbound' ? '(vendor side)' : '(our side)' }}
            </span>
          </label>
          <input
            v-model="localFlow.source_cidr"
            type="text"
            placeholder="10.0.0.0/24"
            class="block w-full rounded-md border-gray-300 font-mono text-sm shadow-sm focus:border-indigo-500 focus:ring-indigo-500"
            :class="{ 'border-red-300': validationErrors.source_cidr }"
          />
          <p v-if="validationErrors.source_cidr" class="mt-1 text-xs text-red-600">
            {{ validationErrors.source_cidr }}
          </p>
        </div>
        <div>
          <label class="mb-1.5 block text-sm font-medium text-gray-700">
            Destination CIDR
            <span class="font-normal text-gray-400">
              {{ localFlow.direction === 'inbound' ? '(our service)' : '(vendor side)' }}
            </span>
          </label>
          <input
            v-model="localFlow.destination_cidr"
            type="text"
            placeholder="172.16.0.0/24"
            class="block w-full rounded-md border-gray-300 font-mono text-sm shadow-sm focus:border-indigo-500 focus:ring-indigo-500"
            :class="{ 'border-red-300': validationErrors.destination_cidr }"
          />
          <p v-if="validationErrors.destination_cidr" class="mt-1 text-xs text-red-600">
            {{ validationErrors.destination_cidr }}
          </p>
          <p class="mt-1 text-xs text-gray-500">
            Private (RFC-1918) destinations must be a /32 host — destination NAT is one-to-one.
            Public destinations aren't NAT'd and may be a range.
          </p>
        </div>
      </div>

      <!-- Protocols / Ports -->
      <div class="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <div>
          <label class="mb-1.5 block text-sm font-medium text-gray-700">Protocols</label>
          <div class="flex flex-wrap items-center gap-2">
            <label
              v-for="proto in ['tcp', 'udp', 'icmp']"
              :key="proto"
              class="flex items-center gap-1.5 rounded-md border px-3 py-1.5 text-sm font-medium transition-colors"
              :class="isAny
                ? 'cursor-not-allowed border-gray-200 bg-gray-50 text-gray-400'
                : (localFlow.protocols.includes(proto)
                  ? 'cursor-pointer border-indigo-600 bg-indigo-50 text-indigo-700'
                  : 'cursor-pointer border-gray-300 text-gray-700 hover:border-gray-400')"
            >
              <input
                type="checkbox"
                class="sr-only"
                :disabled="isAny"
                :checked="localFlow.protocols.includes(proto)"
                @change="toggleProtocol(proto)"
              />
              {{ proto.toUpperCase() }}
            </label>
            <span class="text-gray-300">|</span>
            <label
              class="flex cursor-pointer items-center gap-1.5 rounded-md border px-3 py-1.5 text-sm font-medium transition-colors"
              :class="isAny
                ? 'border-indigo-600 bg-indigo-50 text-indigo-700'
                : 'border-gray-300 text-gray-700 hover:border-gray-400'"
            >
              <input type="checkbox" class="sr-only" :checked="isAny" @change="toggleAny" />
              Any
            </label>
          </div>
          <p v-if="validationErrors.protocols" class="mt-1 text-xs text-red-600">
            {{ validationErrors.protocols }}
          </p>
          <p class="mt-1 text-xs text-gray-500">
            Pick one or more. "Any" matches all IP protocols and can't be combined.
          </p>
        </div>
        <div>
          <label class="mb-1.5 block text-sm font-medium text-gray-700">Destination Ports</label>
          <input
            v-model="localFlow.destination_ports"
            type="text"
            placeholder="443, 8080-8090"
            class="block w-full rounded-md border-gray-300 font-mono text-sm shadow-sm focus:border-indigo-500 focus:ring-indigo-500 disabled:bg-gray-100 disabled:text-gray-400"
            :class="{ 'border-red-300': validationErrors.destination_ports }"
            :disabled="!hasPortProtocol"
          />
          <p v-if="validationErrors.destination_ports" class="mt-1 text-xs text-red-600">
            {{ validationErrors.destination_ports }}
          </p>
          <p v-if="!hasPortProtocol" class="mt-1 text-xs text-gray-400">
            Ports apply to TCP/UDP only.
          </p>
        </div>
      </div>

      <!-- Description -->
      <div>
        <label class="mb-1.5 block text-sm font-medium text-gray-700">
          Description <span class="font-normal text-gray-400">(optional)</span>
        </label>
        <input
          v-model="localFlow.description"
          type="text"
          placeholder="e.g. HL7 results feed to vendor"
          class="block w-full rounded-md border-gray-300 text-sm shadow-sm focus:border-indigo-500 focus:ring-indigo-500"
        />
      </div>
    </div>

    <!-- Actions -->
    <div class="mt-5 flex items-center justify-end gap-3">
      <button
        type="button"
        class="rounded-md border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
        @click="$emit('cancel')"
      >
        Cancel
      </button>
      <button
        type="button"
        class="rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-indigo-700"
        @click="handleSave"
      >
        {{ isNew ? 'Add Flow' : 'Save Changes' }}
      </button>
    </div>
  </div>
</template>

<script setup>
import { computed, reactive, watch } from 'vue'

const props = defineProps({
  flow: {
    type: Object,
    required: true,
  },
  isNew: {
    type: Boolean,
    default: false,
  },
})

const emit = defineEmits(['save', 'cancel'])

function normalizeProtocols(flow) {
  if (Array.isArray(flow.protocols) && flow.protocols.length) return [...flow.protocols]
  if (typeof flow.protocols === 'string' && flow.protocols) {
    return flow.protocols.split(',').map((s) => s.trim()).filter(Boolean)
  }
  // Legacy flows carried a single `protocol`
  if (flow.protocol) return [flow.protocol]
  return ['tcp']
}

const localFlow = reactive({
  ...props.flow,
  // Legacy flows may predate the direction field — default them to outbound
  direction: props.flow.direction || 'outbound',
  protocols: normalizeProtocols(props.flow),
})
delete localFlow.protocol

const isAny = computed(() => localFlow.protocols.includes('any'))
const hasPortProtocol = computed(
  () => localFlow.protocols.includes('tcp') || localFlow.protocols.includes('udp')
)

function toggleProtocol(proto) {
  if (isAny.value) return
  const idx = localFlow.protocols.indexOf(proto)
  if (idx === -1) localFlow.protocols.push(proto)
  else localFlow.protocols.splice(idx, 1)
}

function toggleAny() {
  localFlow.protocols = isAny.value ? ['tcp'] : ['any']
}

const validationErrors = reactive({
  source_cidr: '',
  destination_cidr: '',
  destination_ports: '',
  protocols: '',
})

// Ports only apply to TCP/UDP — clear instead of silently keeping stale input
watch(hasPortProtocol, (has) => {
  if (!has) {
    localFlow.destination_ports = ''
    validationErrors.destination_ports = ''
  }
})

function validateCidr(value) {
  if (!value) return 'Required'
  const cidrRegex = /^(\d{1,3}\.){3}\d{1,3}\/\d{1,2}$/
  if (!cidrRegex.test(value)) return 'Invalid CIDR format (e.g., 10.0.0.0/24)'
  const parts = value.split('/')
  const octets = parts[0].split('.')
  const prefix = parseInt(parts[1])
  if (octets.some((o) => parseInt(o) > 255)) return 'Invalid IP octets'
  if (prefix < 0 || prefix > 32) return 'Prefix must be 0-32'
  return ''
}

function isRfc1918(value) {
  const parts = value.split('/')
  const octets = parts[0].split('.').map(Number)
  if (octets[0] === 10) return true
  if (octets[0] === 172 && octets[1] >= 16 && octets[1] <= 31) return true
  if (octets[0] === 192 && octets[1] === 168) return true
  return false
}

function validateDestinationCidr(value) {
  const base = validateCidr(value)
  if (base) return base
  const prefix = parseInt(value.split('/')[1])
  if (isRfc1918(value) && prefix !== 32) {
    return 'Private (RFC-1918) destinations must be /32 — one flow per host'
  }
  return ''
}

function validatePorts(value) {
  if (!value) return ''
  if (!hasPortProtocol.value) return ''
  const portRegex = /^(\d{1,5}(-\d{1,5})?)(,\s*\d{1,5}(-\d{1,5})?)*$/
  if (!portRegex.test(value.trim())) return 'Invalid format (e.g., 443 or 8080-8090)'
  return ''
}

function handleSave() {
  validationErrors.source_cidr = validateCidr(localFlow.source_cidr)
  validationErrors.destination_cidr = validateDestinationCidr(localFlow.destination_cidr)
  validationErrors.destination_ports = validatePorts(localFlow.destination_ports)
  validationErrors.protocols = localFlow.protocols.length ? '' : 'Select at least one protocol'

  if (
    validationErrors.source_cidr ||
    validationErrors.destination_cidr ||
    validationErrors.destination_ports ||
    validationErrors.protocols
  ) {
    return
  }

  const payload = { ...localFlow }
  if (!hasPortProtocol.value) {
    payload.destination_ports = ''
  }
  emit('save', payload)
}
</script>
