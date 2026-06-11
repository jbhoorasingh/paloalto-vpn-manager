<template>
  <div class="space-y-6">
    <div>
      <h2 class="text-xl font-semibold text-gray-900">Network Topology</h2>
      <p class="mt-1 text-sm text-gray-500">Define the VPN tunnel topology and endpoints.</p>
    </div>

    <div class="grid grid-cols-1 gap-8 lg:grid-cols-2">
      <!-- Configuration panel -->
      <div class="space-y-6">
        <!-- Vendor endpoints count -->
        <div>
          <label class="block text-sm font-medium text-gray-700">Vendor Endpoint Count</label>
          <div class="mt-2 flex gap-4">
            <label class="flex cursor-pointer items-center">
              <input
                type="radio"
                :value="1"
                v-model.number="formData.vendor_endpoints_count"
                class="h-4 w-4 border-gray-300 text-indigo-600 focus:ring-indigo-500"
              />
              <span class="ml-2 text-sm text-gray-700">1 Endpoint</span>
            </label>
            <label class="flex cursor-pointer items-center">
              <input
                type="radio"
                :value="2"
                v-model.number="formData.vendor_endpoints_count"
                class="h-4 w-4 border-gray-300 text-indigo-600 focus:ring-indigo-500"
              />
              <span class="ml-2 text-sm text-gray-700">2 Endpoints</span>
            </label>
          </div>
        </div>

        <!-- Topology type (only shown for 2 endpoints) -->
        <div v-if="formData.vendor_endpoints_count === 2">
          <label for="topology_type" class="block text-sm font-medium text-gray-700">Topology Type</label>
          <select
            id="topology_type"
            v-model="formData.topology_type"
            class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
          >
            <option value="">Select topology type...</option>
            <option value="bow_tie">Bow Tie (Cross-connected)</option>
            <option value="matched_pairs">Matched Pairs (Parallel)</option>
          </select>
        </div>

        <!-- Vendor endpoint IPs -->
        <div>
          <label class="block text-sm font-medium text-gray-700">Vendor Endpoint IP(s)</label>
          <div class="mt-1 space-y-3">
            <div>
              <label class="text-xs text-gray-500">Endpoint 1 IP</label>
              <input
                v-model="formData.vendor_endpoint_1_ip"
                type="text"
                placeholder="e.g., 203.0.113.1"
                class="mt-1 block w-full rounded-md font-mono text-sm shadow-sm focus:border-indigo-500 focus:ring-indigo-500"
                :class="errors.vendor_endpoint_1_ip ? 'border-red-300 focus:border-red-500 focus:ring-red-500' : 'border-gray-300'"
              />
              <p v-if="errors.vendor_endpoint_1_ip" class="mt-1 text-xs text-red-600">{{ errors.vendor_endpoint_1_ip }}</p>
            </div>
            <div v-if="formData.vendor_endpoints_count === 2">
              <label class="text-xs text-gray-500">Endpoint 2 IP</label>
              <input
                v-model="formData.vendor_endpoint_2_ip"
                type="text"
                placeholder="e.g., 203.0.113.2"
                class="mt-1 block w-full rounded-md font-mono text-sm shadow-sm focus:border-indigo-500 focus:ring-indigo-500"
                :class="errors.vendor_endpoint_2_ip ? 'border-red-300 focus:border-red-500 focus:ring-red-500' : 'border-gray-300'"
              />
              <p v-if="errors.vendor_endpoint_2_ip" class="mt-1 text-xs text-red-600">{{ errors.vendor_endpoint_2_ip }}</p>
            </div>
          </div>
        </div>

        <!-- Our endpoint sites -->
        <div>
          <label class="block text-sm font-medium text-gray-700">Our Endpoints</label>
          <p class="mb-2 text-xs text-gray-500">Select our endpoint site(s). Public IP and BGP ASN are managed by administrators.</p>
          <div class="mt-1 space-y-3">
            <div>
              <label class="text-xs text-gray-500">Site 1</label>
              <select
                v-model="formData.our_endpoint_1_site_id"
                class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
              >
                <option :value="null">Select a site...</option>
                <option v-for="site in sites" :key="site.id" :value="site.id">
                  {{ site.name }} ({{ site.code }}){{ site.public_ip ? ' — ' + site.public_ip : '' }}
                </option>
              </select>
              <div v-if="site1Details" class="mt-1 flex gap-4 text-xs text-gray-500">
                <span v-if="site1Details.public_ip">IP: <span class="font-mono">{{ site1Details.public_ip }}</span></span>
                <span v-if="site1Details.bgp_asn">BGP ASN: <span class="font-mono">{{ site1Details.bgp_asn }}</span></span>
              </div>
            </div>
            <div>
              <label class="text-xs text-gray-500">Site 2</label>
              <select
                v-model="formData.our_endpoint_2_site_id"
                class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
              >
                <option :value="null">Select a site...</option>
                <option v-for="site in sites" :key="site.id" :value="site.id">
                  {{ site.name }} ({{ site.code }}){{ site.public_ip ? ' — ' + site.public_ip : '' }}
                </option>
              </select>
              <div v-if="site2Details" class="mt-1 flex gap-4 text-xs text-gray-500">
                <span v-if="site2Details.public_ip">IP: <span class="font-mono">{{ site2Details.public_ip }}</span></span>
                <span v-if="site2Details.bgp_asn">BGP ASN: <span class="font-mono">{{ site2Details.bgp_asn }}</span></span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Live SVG preview -->
      <div>
        <label class="mb-2 block text-sm font-medium text-gray-700">Topology Preview</label>
        <TopologyDiagram
          :vendor-endpoints-count="formData.vendor_endpoints_count"
          :topology-type="formData.topology_type"
          :vendor-endpoint1-ip="formData.vendor_endpoint_1_ip"
          :vendor-endpoint2-ip="formData.vendor_endpoint_2_ip"
          :our-site1-name="site1Name"
          :our-site2-name="site2Name"
        />
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useWizardState } from '../../composables/useWizardState.js'
import TopologyDiagram from '../shared/TopologyDiagram.vue'

const props = defineProps({
  sites: {
    type: Array,
    default: () => [],
  },
})

const { formData, errors } = useWizardState()

const site1Details = computed(() => {
  return props.sites.find((s) => s.id === formData.our_endpoint_1_site_id) || null
})

const site2Details = computed(() => {
  return props.sites.find((s) => s.id === formData.our_endpoint_2_site_id) || null
})

const site1Name = computed(() => {
  const site = site1Details.value
  return site ? `${site.name} (${site.code})` : ''
})

const site2Name = computed(() => {
  const site = site2Details.value
  return site ? `${site.name} (${site.code})` : ''
})
</script>
