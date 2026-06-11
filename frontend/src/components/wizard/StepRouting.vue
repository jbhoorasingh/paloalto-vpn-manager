<template>
  <div class="space-y-6">
    <div>
      <h2 class="text-xl font-semibold text-gray-900">Routing & NAT</h2>
      <p class="mt-1 text-sm text-gray-500">Configure routing protocol and NAT settings.</p>
    </div>

    <!-- Routing Type -->
    <div class="rounded-lg border border-gray-200 bg-white p-6">
      <h3 class="mb-4 text-lg font-medium text-gray-900">Routing Protocol</h3>
      <div class="flex gap-6">
        <label class="flex cursor-pointer items-center">
          <input
            type="radio"
            value="static"
            v-model="formData.routing_type"
            class="h-4 w-4 border-gray-300 text-indigo-600 focus:ring-indigo-500"
          />
          <span class="ml-2 text-sm font-medium text-gray-700">Static Routing</span>
        </label>
        <label class="flex cursor-pointer items-center">
          <input
            type="radio"
            value="bgp"
            v-model="formData.routing_type"
            class="h-4 w-4 border-gray-300 text-indigo-600 focus:ring-indigo-500"
          />
          <span class="ml-2 text-sm font-medium text-gray-700">BGP</span>
        </label>
      </div>

      <!-- Static routing: vendor CIDRs -->
      <Transition
        enter-active-class="transition ease-out duration-200"
        enter-from-class="opacity-0 -translate-y-2"
        enter-to-class="opacity-100 translate-y-0"
        leave-active-class="transition ease-in duration-150"
        leave-from-class="opacity-100 translate-y-0"
        leave-to-class="opacity-0 -translate-y-2"
      >
        <div v-if="formData.routing_type === 'static'" class="mt-6 space-y-4 rounded-md bg-gray-50 p-4">
          <h4 class="text-sm font-medium text-gray-700">Static Route Configuration</h4>

          <!-- Failover warning for static + 2 tunnels -->
          <div v-if="formData.vendor_endpoints_count === 2" class="rounded-md bg-amber-50 border border-amber-200 p-3">
            <div class="flex">
              <svg class="h-5 w-5 flex-shrink-0 text-amber-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z" />
              </svg>
              <p class="ml-2 text-sm text-amber-700">
                Static routing with multiple tunnels requires manual failover on the vendor side and possibly ours.
                Consider using BGP for automatic failover.
              </p>
            </div>
          </div>

          <div>
            <label for="vendor_cidrs" class="block text-sm font-medium text-gray-700">
              Vendor CIDRs <span class="text-red-500">*</span>
            </label>
            <textarea
              id="vendor_cidrs"
              v-model="formData.vendor_cidrs"
              rows="4"
              class="mt-1 block w-full rounded-md border-gray-300 font-mono text-sm shadow-sm focus:border-indigo-500 focus:ring-indigo-500"
              placeholder="10.0.0.0/24&#10;172.16.0.0/16&#10;192.168.1.0/24"
            />
            <p class="mt-1 text-xs text-gray-500">
              Enter the vendor's network CIDRs, one per line. These are the remote networks accessible through the VPN tunnel.
            </p>
          </div>
        </div>
      </Transition>

      <!-- BGP configuration -->
      <Transition
        enter-active-class="transition ease-out duration-200"
        enter-from-class="opacity-0 -translate-y-2"
        enter-to-class="opacity-100 translate-y-0"
        leave-active-class="transition ease-in duration-150"
        leave-from-class="opacity-100 translate-y-0"
        leave-to-class="opacity-0 -translate-y-2"
      >
        <div v-if="formData.routing_type === 'bgp'" class="mt-6 space-y-6 rounded-md bg-gray-50 p-4">
          <h4 class="text-sm font-medium text-gray-700">BGP Configuration</h4>

          <!-- ASN Section -->
          <div>
            <h5 class="mb-3 text-sm font-medium text-gray-600">Vendor Autonomous System Numbers</h5>
            <div class="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div>
                <label for="bgp_remote_asn" class="block text-sm font-medium text-gray-700">
                  Vendor EP1 ASN <span class="text-red-500">*</span>
                </label>
                <input
                  id="bgp_remote_asn"
                  v-model="formData.bgp_remote_asn"
                  type="text"
                  placeholder="e.g., 65100"
                  class="mt-1 block w-full rounded-md font-mono text-sm shadow-sm focus:ring-indigo-500"
                  :class="asnError1 ? 'border-red-300 focus:border-red-500' : 'border-gray-300 focus:border-indigo-500'"
                />
                <p v-if="asnError1" class="mt-1 text-xs text-red-600">{{ asnError1 }}</p>
              </div>
              <div v-if="formData.vendor_endpoints_count === 2">
                <label for="bgp_remote_asn_2" class="block text-sm font-medium text-gray-700">
                  Vendor EP2 ASN
                </label>
                <input
                  id="bgp_remote_asn_2"
                  v-model="formData.bgp_remote_asn_2"
                  type="text"
                  :placeholder="formData.bgp_remote_asn ? 'Same as EP1 if blank' : 'e.g., 65200'"
                  class="mt-1 block w-full rounded-md font-mono text-sm shadow-sm focus:ring-indigo-500"
                  :class="asnError2 ? 'border-red-300 focus:border-red-500' : 'border-gray-300 focus:border-indigo-500'"
                />
                <p v-if="asnError2" class="mt-1 text-xs text-red-600">{{ asnError2 }}</p>
                <p v-else class="mt-1 text-xs text-gray-500">Leave blank if same ASN as EP1.</p>
              </div>
            </div>
          </div>

          <!-- Per-tunnel peering info -->
          <div>
            <h5 class="mb-3 text-sm font-medium text-gray-600">BGP Peering — Per Tunnel</h5>

            <!-- Tunnel table -->
            <div class="overflow-hidden rounded-lg border border-gray-200">
              <table class="min-w-full divide-y divide-gray-200 text-sm">
                <thead class="bg-gray-100">
                  <tr>
                    <th class="px-4 py-2.5 text-left font-medium text-gray-600">Tunnel</th>
                    <th class="px-4 py-2.5 text-left font-medium text-gray-600">Our Site</th>
                    <th class="px-4 py-2.5 text-left font-medium text-gray-600">Our ASN</th>
                    <th class="px-4 py-2.5 text-left font-medium text-gray-600">Vendor EP</th>
                    <th class="px-4 py-2.5 text-left font-medium text-gray-600">Vendor ASN</th>
                  </tr>
                </thead>
                <tbody class="divide-y divide-gray-200 bg-white">
                  <tr v-for="(tunnel, idx) in tunnels" :key="idx">
                    <td class="whitespace-nowrap px-4 py-2.5 font-medium text-gray-900">
                      Tunnel {{ idx + 1 }}
                    </td>
                    <td class="whitespace-nowrap px-4 py-2.5 text-gray-600">
                      {{ tunnel.ourSiteName || 'Not selected' }}
                    </td>
                    <td class="whitespace-nowrap px-4 py-2.5">
                      <span v-if="tunnel.ourAsn" class="rounded bg-indigo-50 px-2 py-0.5 font-mono text-indigo-700">
                        {{ tunnel.ourAsn }}
                      </span>
                      <span v-else class="text-gray-400">--</span>
                    </td>
                    <td class="whitespace-nowrap px-4 py-2.5 text-gray-600">
                      {{ tunnel.vendorEpLabel }}
                      <span v-if="tunnel.vendorIp" class="ml-1 font-mono text-gray-400">
                        ({{ tunnel.vendorIp }})
                      </span>
                    </td>
                    <td class="whitespace-nowrap px-4 py-2.5">
                      <span v-if="tunnel.vendorAsn" class="rounded bg-amber-50 px-2 py-0.5 font-mono text-amber-700">
                        {{ tunnel.vendorAsn }}
                      </span>
                      <span v-else class="text-gray-400">--</span>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>

            <p class="mt-2 text-xs text-gray-500">
              Each tunnel between our sites and vendor endpoints establishes a separate BGP peering session.
              Our ASN is automatically derived from the endpoint configuration.
            </p>
          </div>

          <!-- BGP Auth -->
          <div>
            <label class="flex items-center">
              <input
                type="checkbox"
                v-model="formData.bgp_auth_enabled"
                class="h-4 w-4 rounded border-gray-300 text-indigo-600 focus:ring-indigo-500"
              />
              <span class="ml-2 text-sm text-gray-700">BGP Authentication Enabled (MD5)</span>
            </label>
          </div>
        </div>
      </Transition>
    </div>

    <!-- Tunnel IP Assignment (visible once routing_type is selected) -->
    <Transition
      enter-active-class="transition ease-out duration-200"
      enter-from-class="opacity-0 -translate-y-2"
      enter-to-class="opacity-100 translate-y-0"
      leave-active-class="transition ease-in duration-150"
      leave-from-class="opacity-100 translate-y-0"
      leave-to-class="opacity-0 -translate-y-2"
    >
      <div v-if="formData.routing_type" class="rounded-lg border border-gray-200 bg-white p-6">
        <h3 class="mb-2 text-lg font-medium text-gray-900">Tunnel Interface IP Assignment</h3>
        <p class="mb-4 text-sm text-gray-500">
          Each VPN tunnel requires IP addresses on the tunnel interfaces. Select how these will be assigned.
        </p>
        <div class="space-y-2">
          <label class="flex cursor-pointer items-start gap-2 rounded-md border border-gray-200 bg-white p-3 hover:bg-gray-50 transition-colors"
                 :class="formData.tunnel_ip_assignment === 'we_assign' ? 'border-indigo-300 ring-1 ring-indigo-200' : ''">
            <input
              type="radio"
              value="we_assign"
              v-model="formData.tunnel_ip_assignment"
              class="mt-0.5 h-4 w-4 border-gray-300 text-indigo-600 focus:ring-indigo-500"
            />
            <div>
              <span class="text-sm font-medium text-gray-900">We assign from tunnel IP pool</span>
              <p class="text-xs text-gray-500">IPs will be auto-assigned from our dynamic tunnel interface pool during provisioning.</p>
            </div>
          </label>
          <label class="flex cursor-pointer items-start gap-2 rounded-md border border-gray-200 bg-white p-3 hover:bg-gray-50 transition-colors"
                 :class="formData.tunnel_ip_assignment === 'mutual' ? 'border-indigo-300 ring-1 ring-indigo-200' : ''">
            <input
              type="radio"
              value="mutual"
              v-model="formData.tunnel_ip_assignment"
              class="mt-0.5 h-4 w-4 border-gray-300 text-indigo-600 focus:ring-indigo-500"
            />
            <div>
              <span class="text-sm font-medium text-gray-900">Mutually agreed</span>
              <p class="text-xs text-gray-500">Both parties will agree on tunnel interface IPs. Specify them per tunnel below.</p>
            </div>
          </label>
          <label class="flex cursor-pointer items-start gap-2 rounded-md border border-gray-200 bg-white p-3 hover:bg-gray-50 transition-colors"
                 :class="formData.tunnel_ip_assignment === 'apipa' ? 'border-indigo-300 ring-1 ring-indigo-200' : ''">
            <input
              type="radio"
              value="apipa"
              v-model="formData.tunnel_ip_assignment"
              class="mt-0.5 h-4 w-4 border-gray-300 text-indigo-600 focus:ring-indigo-500"
            />
            <div>
              <span class="text-sm font-medium text-gray-900">APIPA (169.254.x.x)</span>
              <p class="text-xs text-gray-500">Use link-local addresses when the vendor doesn't support routable tunnel IPs.</p>
            </div>
          </label>
        </div>

        <!-- Per-tunnel mutual IP inputs -->
        <Transition
          enter-active-class="transition ease-out duration-200"
          enter-from-class="opacity-0 -translate-y-2"
          enter-to-class="opacity-100 translate-y-0"
          leave-active-class="transition ease-in duration-150"
          leave-from-class="opacity-100 translate-y-0"
          leave-to-class="opacity-0 -translate-y-2"
        >
          <div v-if="formData.tunnel_ip_assignment === 'mutual'" class="mt-4 space-y-3">
            <h4 class="text-sm font-medium text-gray-700">Per-Tunnel IP Addresses</h4>
            <div class="overflow-hidden rounded-lg border border-gray-200">
              <table class="min-w-full divide-y divide-gray-200 text-sm">
                <thead class="bg-gray-100">
                  <tr>
                    <th class="px-4 py-2.5 text-left font-medium text-gray-600">Tunnel</th>
                    <th class="px-4 py-2.5 text-left font-medium text-gray-600">Our Site</th>
                    <th class="px-4 py-2.5 text-left font-medium text-gray-600">Local IP (ours)</th>
                    <th class="px-4 py-2.5 text-left font-medium text-gray-600">Remote IP (vendor)</th>
                  </tr>
                </thead>
                <tbody class="divide-y divide-gray-200 bg-white">
                  <tr v-for="(tunnel, idx) in tunnels" :key="idx">
                    <td class="whitespace-nowrap px-4 py-2.5 font-medium text-gray-900">
                      Tunnel {{ idx + 1 }}
                    </td>
                    <td class="whitespace-nowrap px-4 py-2.5 text-gray-600">
                      {{ tunnel.ourSiteName || 'Not selected' }}
                    </td>
                    <td class="px-4 py-2.5">
                      <input
                        type="text"
                        v-model="mutualIps[idx].local_ip"
                        placeholder="e.g. 10.0.0.1"
                        class="w-full rounded-md border-gray-300 font-mono text-sm shadow-sm focus:border-indigo-500 focus:ring-indigo-500"
                      />
                    </td>
                    <td class="px-4 py-2.5">
                      <input
                        type="text"
                        v-model="mutualIps[idx].remote_ip"
                        placeholder="e.g. 10.0.0.2"
                        class="w-full rounded-md border-gray-300 font-mono text-sm shadow-sm focus:border-indigo-500 focus:ring-indigo-500"
                      />
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
            <p class="text-xs text-gray-500">
              Enter the agreed-upon IP addresses for each tunnel interface.
            </p>
          </div>
        </Transition>
      </div>
    </Transition>

    <!-- NAT Section -->
    <div class="rounded-lg border border-gray-200 bg-white p-6">
      <h3 class="mb-4 text-lg font-medium text-gray-900">NAT Configuration</h3>
      <div>
        <label class="block text-sm font-medium text-gray-700">Does the vendor support NAT?</label>
        <div class="mt-2 flex gap-6">
          <label class="flex cursor-pointer items-center">
            <input
              type="radio"
              :value="true"
              v-model="formData.nat_supported"
              class="h-4 w-4 border-gray-300 text-indigo-600 focus:ring-indigo-500"
            />
            <span class="ml-2 text-sm text-gray-700">Yes</span>
          </label>
          <label class="flex cursor-pointer items-center">
            <input
              type="radio"
              :value="false"
              v-model="formData.nat_supported"
              class="h-4 w-4 border-gray-300 text-indigo-600 focus:ring-indigo-500"
            />
            <span class="ml-2 text-sm text-gray-700">No</span>
          </label>
          <label class="flex cursor-pointer items-center">
            <input
              type="radio"
              :value="null"
              v-model="formData.nat_supported"
              class="h-4 w-4 border-gray-300 text-indigo-600 focus:ring-indigo-500"
            />
            <span class="ml-2 text-sm text-gray-700">Not Sure</span>
          </label>
        </div>
      </div>

      <!-- Exception reason when No -->
      <Transition
        enter-active-class="transition ease-out duration-200"
        enter-from-class="opacity-0 -translate-y-2"
        enter-to-class="opacity-100 translate-y-0"
        leave-active-class="transition ease-in duration-150"
        leave-from-class="opacity-100 translate-y-0"
        leave-to-class="opacity-0 -translate-y-2"
      >
        <div v-if="formData.nat_supported === false" class="mt-4">
          <label for="nat_exception_reason" class="block text-sm font-medium text-gray-700">
            Exception Reason
          </label>
          <textarea
            id="nat_exception_reason"
            v-model="formData.nat_exception_reason"
            rows="3"
            class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
            placeholder="Explain why NAT is not supported..."
          />
          <p class="mt-1 text-xs text-gray-500">
            A reason is required when NAT is not supported to justify the exception.
          </p>
        </div>
      </Transition>
    </div>
  </div>
</template>

<script setup>
import { computed, reactive, watch } from 'vue'
import { useWizardState } from '../../composables/useWizardState.js'

const props = defineProps({
  sites: {
    type: Array,
    default: () => [],
  },
})

const { formData, errors } = useWizardState()

// ASN validation
function validateAsn(value) {
  if (!value && value !== 0) return null // empty is ok (optional)
  const num = Number(value)
  if (!Number.isInteger(num) || num < 1 || num > 4294967295) {
    return 'Must be a number between 1 and 4,294,967,295'
  }
  return null
}

const asnError1 = computed(() => errors.value?.bgp_remote_asn || validateAsn(formData.bgp_remote_asn))
const asnError2 = computed(() => errors.value?.bgp_remote_asn_2 || validateAsn(formData.bgp_remote_asn_2))

// Helper to look up site details
function getSite(siteId) {
  return props.sites.find((s) => s.id === siteId) || null
}

// Resolve vendor ASN for a given endpoint number (1 or 2)
function vendorAsnForEp(epNum) {
  if (epNum === 2) {
    return formData.bgp_remote_asn_2 || formData.bgp_remote_asn || null
  }
  return formData.bgp_remote_asn || null
}

// Build tunnel list based on topology
const tunnels = computed(() => {
  const site1 = getSite(formData.our_endpoint_1_site_id)
  const site2 = getSite(formData.our_endpoint_2_site_id)
  const ep1Ip = formData.vendor_endpoint_1_ip
  const ep2Ip = formData.vendor_endpoint_2_ip
  const count = formData.vendor_endpoints_count
  const topo = formData.topology_type

  const makeTunnel = (site, epNum, epIp) => ({
    ourSiteName: site ? `${site.name} (${site.code})` : '',
    ourAsn: site?.bgp_asn || null,
    vendorEpLabel: `Vendor EP${epNum}`,
    vendorIp: epIp || '',
    vendorAsn: vendorAsnForEp(epNum),
  })

  const list = []

  if (count === 1) {
    // Both our sites connect to vendor EP1
    list.push(makeTunnel(site1, 1, ep1Ip))
    list.push(makeTunnel(site2, 1, ep1Ip))
  } else if (count === 2 && topo === 'bow_tie') {
    // All four cross-connections
    list.push(makeTunnel(site1, 1, ep1Ip))
    list.push(makeTunnel(site1, 2, ep2Ip))
    list.push(makeTunnel(site2, 1, ep1Ip))
    list.push(makeTunnel(site2, 2, ep2Ip))
  } else {
    // Matched pairs or default (2 endpoints, no topology yet)
    list.push(makeTunnel(site1, 1, ep1Ip))
    list.push(makeTunnel(site2, 2, ep2Ip))
  }

  return list
})

// Mutual IPs — reactive array synced to formData.mutual_tunnel_ips
const mutualIps = reactive(parseMutualIps())

function parseMutualIps() {
  try {
    const parsed = JSON.parse(formData.mutual_tunnel_ips || '[]')
    return Array.isArray(parsed) ? parsed : []
  } catch {
    return []
  }
}

// Keep mutualIps array in sync with tunnel count
watch(
  () => tunnels.value.length,
  (newLen) => {
    while (mutualIps.length < newLen) {
      mutualIps.push({ local_ip: '', remote_ip: '' })
    }
    while (mutualIps.length > newLen) {
      mutualIps.pop()
    }
  },
  { immediate: true }
)

// Serialize mutualIps back to formData when changed
watch(
  mutualIps,
  (val) => {
    formData.mutual_tunnel_ips = JSON.stringify(val)
  },
  { deep: true }
)
</script>
