<template>
  <div class="relative">
    <svg
      viewBox="0 0 500 300"
      xmlns="http://www.w3.org/2000/svg"
      class="w-full rounded-lg border border-gray-200 bg-white"
    >
      <!-- Left side: Our Sites -->
      <g>
        <!-- Our Region 1 -->
        <rect x="20" y="60" width="130" height="60" rx="8" fill="#EEF2FF" stroke="#6366F1" stroke-width="1.5" />
        <text x="85" y="85" text-anchor="middle" class="text-xs" fill="#4338CA" font-size="12" font-weight="600">
          {{ ourSite1Label }}
        </text>
        <text x="85" y="105" text-anchor="middle" fill="#6366F1" font-size="10">
          Our Region 1
        </text>

        <!-- Our Region 2 -->
        <rect x="20" y="180" width="130" height="60" rx="8" fill="#EEF2FF" stroke="#6366F1" stroke-width="1.5" />
        <text x="85" y="205" text-anchor="middle" class="text-xs" fill="#4338CA" font-size="12" font-weight="600">
          {{ ourSite2Label }}
        </text>
        <text x="85" y="225" text-anchor="middle" fill="#6366F1" font-size="10">
          Our Region 2
        </text>
      </g>

      <!-- Right side: Vendor Endpoints -->
      <g>
        <!-- Vendor EP 1 -->
        <rect x="350" y="60" width="130" height="60" rx="8" fill="#FEF3C7" stroke="#D97706" stroke-width="1.5" />
        <text x="415" y="85" text-anchor="middle" fill="#92400E" font-size="12" font-weight="600">
          Vendor EP1
        </text>
        <text x="415" y="105" text-anchor="middle" fill="#D97706" font-size="10">
          {{ vendorEndpoint1Ip || 'IP TBD' }}
        </text>

        <!-- Vendor EP 2 (conditional) -->
        <g v-if="vendorEndpointsCount === 2">
          <rect x="350" y="180" width="130" height="60" rx="8" fill="#FEF3C7" stroke="#D97706" stroke-width="1.5" />
          <text x="415" y="205" text-anchor="middle" fill="#92400E" font-size="12" font-weight="600">
            Vendor EP2
          </text>
          <text x="415" y="225" text-anchor="middle" fill="#D97706" font-size="10">
            {{ vendorEndpoint2Ip || 'IP TBD' }}
          </text>
        </g>

        <!-- Single endpoint centered -->
        <g v-if="vendorEndpointsCount === 1">
          <rect x="350" y="180" width="130" height="60" rx="8" fill="#F3F4F6" stroke="#D1D5DB" stroke-width="1" stroke-dasharray="4 2" />
          <text x="415" y="215" text-anchor="middle" fill="#9CA3AF" font-size="11">
            (Single EP)
          </text>
        </g>
      </g>

      <!-- Connection lines -->
      <g stroke-width="2" fill="none">
        <!-- Bow Tie: both our sites connect to both vendor EPs -->
        <template v-if="topologyType === 'bow_tie' && vendorEndpointsCount === 2">
          <!-- Region 1 -> EP1 -->
          <line x1="150" y1="80" x2="350" y2="80" stroke="#6366F1" stroke-width="2" />
          <!-- Region 1 -> EP2 -->
          <line x1="150" y1="100" x2="350" y2="200" stroke="#6366F1" stroke-width="2" stroke-dasharray="6 3" />
          <!-- Region 2 -> EP1 -->
          <line x1="150" y1="200" x2="350" y2="100" stroke="#6366F1" stroke-width="2" stroke-dasharray="6 3" />
          <!-- Region 2 -> EP2 -->
          <line x1="150" y1="220" x2="350" y2="220" stroke="#6366F1" stroke-width="2" />
        </template>

        <!-- Matched Pairs: Region1<->EP1, Region2<->EP2 -->
        <template v-else-if="topologyType === 'matched_pairs' && vendorEndpointsCount === 2">
          <line x1="150" y1="90" x2="350" y2="90" stroke="#6366F1" stroke-width="2" />
          <line x1="150" y1="210" x2="350" y2="210" stroke="#6366F1" stroke-width="2" />
        </template>

        <!-- Single endpoint: both regions connect to EP1 -->
        <template v-else-if="vendorEndpointsCount === 1">
          <line x1="150" y1="90" x2="350" y2="90" stroke="#6366F1" stroke-width="2" />
          <line x1="150" y1="210" x2="350" y2="90" stroke="#6366F1" stroke-width="2" stroke-dasharray="6 3" />
        </template>

        <!-- Default: no topology selected yet -->
        <template v-else>
          <line x1="150" y1="90" x2="350" y2="90" stroke="#D1D5DB" stroke-width="1.5" stroke-dasharray="4 2" />
          <line x1="150" y1="210" x2="350" y2="210" stroke="#D1D5DB" stroke-width="1.5" stroke-dasharray="4 2" />
        </template>
      </g>

      <!-- Title -->
      <text x="250" y="25" text-anchor="middle" fill="#374151" font-size="13" font-weight="600">
        Topology Preview
      </text>

      <!-- Legend for topology type -->
      <text x="250" y="285" text-anchor="middle" fill="#6B7280" font-size="10">
        {{ topologyLabel }}
      </text>
    </svg>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  vendorEndpointsCount: {
    type: Number,
    default: 1,
    validator: (v) => [1, 2].includes(v),
  },
  topologyType: {
    type: String,
    default: '',
  },
  vendorEndpoint1Ip: {
    type: String,
    default: '',
  },
  vendorEndpoint2Ip: {
    type: String,
    default: '',
  },
  ourSite1Name: {
    type: String,
    default: '',
  },
  ourSite2Name: {
    type: String,
    default: '',
  },
})

const ourSite1Label = computed(() => props.ourSite1Name || 'Site 1')
const ourSite2Label = computed(() => props.ourSite2Name || 'Site 2')

const topologyLabels = {
  bow_tie: 'Bow Tie - Cross-connected (X pattern)',
  matched_pairs: 'Matched Pairs - Parallel connections',
}

const topologyLabel = computed(() => {
  if (!props.topologyType) return 'Select a topology type above'
  return topologyLabels[props.topologyType] || props.topologyType
})
</script>
