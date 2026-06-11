<template>
  <div class="relative">
    <!-- Loading -->
    <div v-if="loading" class="flex items-center justify-center py-10">
      <svg class="mr-2 h-5 w-5 animate-spin text-indigo-600" fill="none" viewBox="0 0 24 24">
        <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
        <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
      </svg>
      <span class="text-sm text-gray-500">Loading flows...</span>
    </div>

    <!-- No flows -->
    <div v-else-if="flows.length === 0" class="rounded-md bg-gray-50 py-8 text-center">
      <svg class="mx-auto h-10 w-10 text-gray-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M8 7h12m0 0l-4-4m4 4l-4 4m0 6H4m0 0l4 4m-4-4l4-4" />
      </svg>
      <p class="mt-2 text-sm text-gray-500">No traffic flows defined yet.</p>
    </div>

    <!-- Diagram -->
    <template v-else>
      <svg
        :viewBox="`0 0 ${svgWidth} ${svgHeight}`"
        xmlns="http://www.w3.org/2000/svg"
        class="w-full rounded-lg border border-gray-200 bg-white"
      >
        <!-- Defs: arrow marker -->
        <defs>
          <marker id="flow-arrow" viewBox="0 0 10 6" refX="10" refY="3" markerWidth="8" markerHeight="6" orient="auto">
            <path d="M0,0 L10,3 L0,6 Z" fill="#6366F1" />
          </marker>
        </defs>

        <!-- Title -->
        <text :x="svgWidth / 2" y="22" text-anchor="middle" fill="#374151" font-size="13" font-weight="600">
          Traffic Flow Diagram
        </text>

        <!-- Column headers -->
        <text x="90" y="48" text-anchor="middle" fill="#6B7280" font-size="11" font-weight="500">Sources</text>
        <text :x="svgWidth - 90" y="48" text-anchor="middle" fill="#6B7280" font-size="11" font-weight="500">Destinations</text>

        <!-- Source bubbles (left) -->
        <g v-for="(src, i) in sources" :key="'s-' + i">
          <rect
            x="10"
            :y="src.y"
            width="160"
            :height="src.height"
            rx="8"
            fill="#EEF2FF"
            stroke="#6366F1"
            stroke-width="1.5"
          />
          <text
            x="90"
            :y="src.y + 20"
            text-anchor="middle"
            fill="#4338CA"
            font-size="11"
            font-weight="600"
          >{{ src.cidr }}</text>
          <text
            v-for="(line, li) in src.descLines"
            :key="li"
            x="90"
            :y="src.y + 34 + li * 13"
            text-anchor="middle"
            fill="#6366F1"
            font-size="9"
          >{{ line }}</text>
        </g>

        <!-- Destination bubbles (right) -->
        <g v-for="(dst, i) in destinations" :key="'d-' + i">
          <rect
            :x="svgWidth - 170"
            :y="dst.y"
            width="160"
            :height="dst.height"
            rx="8"
            fill="#FEF3C7"
            stroke="#D97706"
            stroke-width="1.5"
          />
          <text
            :x="svgWidth - 90"
            :y="dst.y + 20"
            text-anchor="middle"
            fill="#92400E"
            font-size="11"
            font-weight="600"
          >{{ dst.cidr }}</text>
          <text
            v-for="(line, li) in dst.descLines"
            :key="li"
            :x="svgWidth - 90"
            :y="dst.y + 34 + li * 13"
            text-anchor="middle"
            fill="#D97706"
            font-size="9"
          >{{ line }}</text>
        </g>

        <!-- Connection lines with protocol/port labels -->
        <g v-for="(conn, i) in connections" :key="'c-' + i">
          <line
            :x1="170"
            :y1="conn.srcY"
            :x2="svgWidth - 170"
            :y2="conn.dstY"
            stroke="#6366F1"
            stroke-width="1.5"
            marker-end="url(#flow-arrow)"
          />
          <!-- Label on the line -->
          <rect
            :x="(svgWidth / 2) - conn.labelWidth / 2 - 4"
            :y="conn.labelY - 10"
            :width="conn.labelWidth + 8"
            height="16"
            rx="4"
            fill="#EEF2FF"
          />
          <text
            :x="svgWidth / 2"
            :y="conn.labelY"
            text-anchor="middle"
            fill="#4338CA"
            font-size="9"
            font-weight="500"
          >{{ conn.label }}</text>
        </g>
      </svg>

      <!-- Flow summary table below diagram -->
      <div class="mt-3 overflow-hidden rounded-lg border border-gray-200">
        <table class="min-w-full divide-y divide-gray-200 text-xs">
          <thead class="bg-gray-50">
            <tr>
              <th class="px-3 py-2 text-left font-medium text-gray-500">Source</th>
              <th class="px-3 py-2 text-left font-medium text-gray-500">Destination</th>
              <th class="px-3 py-2 text-left font-medium text-gray-500">Direction</th>
              <th class="px-3 py-2 text-left font-medium text-gray-500">Protocol</th>
              <th class="px-3 py-2 text-left font-medium text-gray-500">Ports</th>
              <th class="px-3 py-2 text-left font-medium text-gray-500">Description</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-gray-200 bg-white">
            <tr v-for="flow in flows" :key="flow.id">
              <td class="whitespace-nowrap px-3 py-1.5 font-mono text-gray-900">{{ flow.source_cidr }}</td>
              <td class="whitespace-nowrap px-3 py-1.5 font-mono text-gray-900">{{ flow.destination_cidr }}</td>
              <td class="whitespace-nowrap px-3 py-1.5">
                <span
                  v-if="flow.direction === 'outbound'"
                  class="inline-flex items-center rounded-full bg-blue-50 px-2 py-0.5 font-medium text-blue-700"
                >Outbound &rarr;</span>
                <span
                  v-else-if="flow.direction === 'inbound'"
                  class="inline-flex items-center rounded-full bg-emerald-50 px-2 py-0.5 font-medium text-emerald-700"
                >&larr; Inbound</span>
                <span v-else class="text-gray-400">--</span>
              </td>
              <td class="whitespace-nowrap px-3 py-1.5 text-gray-600">{{ flow.protocol.toUpperCase() }}</td>
              <td class="whitespace-nowrap px-3 py-1.5 font-mono text-gray-600">{{ flow.destination_ports || 'any' }}</td>
              <td class="px-3 py-1.5 text-gray-500">{{ flow.description || '---' }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useApi } from '../../composables/useApi.js'

const props = defineProps({
  requestId: {
    type: [String, Number],
    required: true,
  },
})

const { apiFetch } = useApi()
const flows = ref([])
const loading = ref(true)

onMounted(async () => {
  const result = await apiFetch(`/api/vpn/requests/${props.requestId}/flows/`)
  if (result.ok) {
    flows.value = result.data.flows || []
  }
  loading.value = false
})

// Group unique source CIDRs
const sources = computed(() => {
  const map = new Map()
  for (const f of flows.value) {
    if (!map.has(f.source_cidr)) {
      map.set(f.source_cidr, [])
    }
    map.get(f.source_cidr).push(f)
  }
  const items = []
  const startY = 60
  const gap = 12
  let y = startY
  for (const [cidr, fls] of map) {
    const descLines = [...new Set(fls.map((f) => f.description).filter(Boolean))].slice(0, 2)
    const height = 30 + descLines.length * 13
    items.push({ cidr, y, height, descLines, flows: fls })
    y += height + gap
  }
  return items
})

// Group unique destination CIDRs
const destinations = computed(() => {
  const map = new Map()
  for (const f of flows.value) {
    if (!map.has(f.destination_cidr)) {
      map.set(f.destination_cidr, [])
    }
    map.get(f.destination_cidr).push(f)
  }
  const items = []
  const startY = 60
  const gap = 12
  let y = startY
  for (const [cidr, fls] of map) {
    const descLines = [...new Set(fls.map((f) => f.description).filter(Boolean))].slice(0, 2)
    const height = 30 + descLines.length * 13
    items.push({ cidr, y, height, descLines, flows: fls })
    y += height + gap
  }
  return items
})

// Build connection lines
const connections = computed(() => {
  const srcMap = new Map()
  sources.value.forEach((s) => srcMap.set(s.cidr, s))
  const dstMap = new Map()
  destinations.value.forEach((d) => dstMap.set(d.cidr, d))

  const lines = []
  const labelOffsets = new Map()

  for (const flow of flows.value) {
    const src = srcMap.get(flow.source_cidr)
    const dst = dstMap.get(flow.destination_cidr)
    if (!src || !dst) continue

    const srcY = src.y + src.height / 2
    const dstY = dst.y + dst.height / 2
    const midY = (srcY + dstY) / 2

    // Offset labels that overlap
    const key = `${Math.round(midY)}`
    const offset = labelOffsets.get(key) || 0
    labelOffsets.set(key, offset + 1)
    const labelY = midY + offset * 16

    const proto = flow.protocol.toUpperCase()
    const ports = flow.destination_ports || 'any'
    const label = proto === 'ICMP' || proto === 'ANY' ? proto : `${proto}/${ports}`

    lines.push({
      srcY,
      dstY,
      label,
      labelY,
      labelWidth: label.length * 5.5 + 4,
    })
  }
  return lines
})

// Dynamic SVG height
const svgHeight = computed(() => {
  const srcBottom = sources.value.length ? Math.max(...sources.value.map((s) => s.y + s.height)) : 60
  const dstBottom = destinations.value.length ? Math.max(...destinations.value.map((d) => d.y + d.height)) : 60
  return Math.max(srcBottom, dstBottom) + 30
})

const svgWidth = 520
</script>
