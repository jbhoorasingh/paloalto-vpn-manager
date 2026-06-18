<template>
  <div class="space-y-6">
    <div>
      <h2 class="text-xl font-semibold text-gray-900">Review & Submit</h2>
      <p class="mt-1 text-sm text-gray-500">Review all information before submitting your VPN request.</p>
    </div>

    <!-- Validation errors -->
    <div v-if="Object.keys(errors).length > 0" class="rounded-md border border-red-200 bg-red-50 p-4">
      <div class="flex">
        <svg class="h-5 w-5 flex-shrink-0 text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
        <div class="ml-3">
          <h3 class="text-sm font-medium text-red-800">Please fix the following errors:</h3>
          <ul class="mt-2 list-inside list-disc text-sm text-red-700">
            <li v-for="(msg, field) in errors" :key="field">{{ field }}: {{ msg }}</li>
          </ul>
        </div>
      </div>
    </div>

    <!-- Vendor Section -->
    <div class="rounded-lg border border-gray-200 bg-white">
      <div class="flex items-center justify-between border-b border-gray-200 px-6 py-4">
        <h3 class="text-base font-semibold text-gray-900">Vendor</h3>
        <button type="button" class="text-sm font-medium text-indigo-600 hover:text-indigo-500" @click="goToStep(1)">Edit</button>
      </div>
      <div class="px-6 py-4">
        <div class="flex py-1.5">
          <dt class="w-40 flex-shrink-0 text-sm font-medium text-gray-500">Vendor</dt>
          <dd class="text-sm text-gray-900">{{ formData.vendor_name || 'Not selected' }}</dd>
        </div>
      </div>
    </div>

    <!-- Apps & Data Section -->
    <div class="rounded-lg border border-gray-200 bg-white">
      <div class="flex items-center justify-between border-b border-gray-200 px-6 py-4">
        <h3 class="text-base font-semibold text-gray-900">Applications & Data</h3>
        <button type="button" class="text-sm font-medium text-indigo-600 hover:text-indigo-500" @click="goToStep(2)">Edit</button>
      </div>
      <div class="px-6 py-4">
        <div class="flex py-1.5">
          <dt class="w-40 flex-shrink-0 text-sm font-medium text-gray-500">Title</dt>
          <dd class="text-sm text-gray-900">{{ formData.title || '---' }}</dd>
        </div>
        <div class="flex py-1.5">
          <dt class="w-40 flex-shrink-0 text-sm font-medium text-gray-500">Purpose</dt>
          <dd class="text-sm text-gray-900">{{ formData.purpose || '---' }}</dd>
        </div>
        <div class="flex py-1.5">
          <dt class="w-40 flex-shrink-0 text-sm font-medium text-gray-500">Applications</dt>
          <dd class="text-sm text-gray-900">{{ applicationNames }}</dd>
        </div>
        <div class="flex py-1.5">
          <dt class="w-40 flex-shrink-0 text-sm font-medium text-gray-500">Directionality</dt>
          <dd class="text-sm text-gray-900">{{ directionalityLabel }}</dd>
        </div>
        <div class="flex py-1.5">
          <dt class="w-40 flex-shrink-0 text-sm font-medium text-gray-500">Data Description</dt>
          <dd class="text-sm text-gray-900">{{ formData.data_description || '---' }}</dd>
        </div>
        <div class="flex py-1.5">
          <dt class="w-40 flex-shrink-0 text-sm font-medium text-gray-500">Data Classification</dt>
          <dd class="text-sm text-gray-900">{{ classificationLabel }}</dd>
        </div>
      </div>
    </div>

    <!-- Topology Section -->
    <div class="rounded-lg border border-gray-200 bg-white">
      <div class="flex items-center justify-between border-b border-gray-200 px-6 py-4">
        <h3 class="text-base font-semibold text-gray-900">Network Topology</h3>
        <button type="button" class="text-sm font-medium text-indigo-600 hover:text-indigo-500" @click="goToStep(3)">Edit</button>
      </div>
      <div class="px-6 py-4">
        <div class="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <div>
            <div class="flex py-1.5">
              <dt class="w-40 flex-shrink-0 text-sm font-medium text-gray-500">Vendor Endpoints</dt>
              <dd class="text-sm text-gray-900">{{ formData.vendor_endpoints_count }}</dd>
            </div>
            <div class="flex py-1.5">
              <dt class="w-40 flex-shrink-0 text-sm font-medium text-gray-500">Topology Type</dt>
              <dd class="text-sm text-gray-900">{{ topologyLabel }}</dd>
            </div>
            <div class="flex py-1.5">
              <dt class="w-40 flex-shrink-0 text-sm font-medium text-gray-500">Vendor EP1 IP</dt>
              <dd class="text-sm text-gray-900">{{ formData.vendor_endpoint_1_ip || 'Not set' }}</dd>
            </div>
            <div v-if="formData.vendor_endpoints_count === 2" class="flex py-1.5">
              <dt class="w-40 flex-shrink-0 text-sm font-medium text-gray-500">Vendor EP2 IP</dt>
              <dd class="text-sm text-gray-900">{{ formData.vendor_endpoint_2_ip || 'Not set' }}</dd>
            </div>
            <div class="flex py-1.5">
              <dt class="w-40 flex-shrink-0 text-sm font-medium text-gray-500">Our Site 1</dt>
              <dd class="text-sm text-gray-900">{{ site1Name || 'Not selected' }}</dd>
            </div>
            <div v-if="formData.our_endpoints_count === 2" class="flex py-1.5">
              <dt class="w-40 flex-shrink-0 text-sm font-medium text-gray-500">Our Site 2</dt>
              <dd class="text-sm text-gray-900">{{ site2Name || 'Not selected' }}</dd>
            </div>
          </div>
          <div>
            <TopologyDiagram
              :vendor-endpoints-count="formData.vendor_endpoints_count"
              :our-endpoints-count="formData.our_endpoints_count"
              :topology-type="formData.topology_type"
              :vendor-endpoint1-ip="formData.vendor_endpoint_1_ip"
              :vendor-endpoint2-ip="formData.vendor_endpoint_2_ip"
              :our-site1-name="site1Name"
              :our-site2-name="site2Name"
            />
          </div>
        </div>
      </div>
    </div>

    <!-- Crypto Section -->
    <div class="rounded-lg border border-gray-200 bg-white">
      <div class="flex items-center justify-between border-b border-gray-200 px-6 py-4">
        <h3 class="text-base font-semibold text-gray-900">Cryptographic Settings</h3>
        <button type="button" class="text-sm font-medium text-indigo-600 hover:text-indigo-500" @click="goToStep(4)">Edit</button>
      </div>
      <div class="px-6 py-4">
        <div class="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div>
            <h4 class="mb-2 text-sm font-semibold text-gray-700">IKE Phase 1</h4>
            <div class="flex py-1.5">
              <dt class="w-40 flex-shrink-0 text-sm font-medium text-gray-500">Version</dt>
              <dd class="text-sm text-gray-900">IKEv{{ formData.ike_version }}</dd>
            </div>
            <div class="flex py-1.5">
              <dt class="w-40 flex-shrink-0 text-sm font-medium text-gray-500">Auth Method</dt>
              <dd class="text-sm text-gray-900">{{ formData.auth_method === 'psk' ? 'Pre-Shared Key' : 'Certificate' }}</dd>
            </div>
            <div class="flex py-1.5">
              <dt class="w-40 flex-shrink-0 text-sm font-medium text-gray-500">Encryption</dt>
              <dd class="text-sm text-gray-900">{{ formData.ike_encryption?.toUpperCase() || '---' }}</dd>
            </div>
            <div class="flex py-1.5">
              <dt class="w-40 flex-shrink-0 text-sm font-medium text-gray-500">Integrity</dt>
              <dd class="text-sm text-gray-900">{{ formData.ike_integrity?.toUpperCase() || '---' }}</dd>
            </div>
            <div class="flex py-1.5">
              <dt class="w-40 flex-shrink-0 text-sm font-medium text-gray-500">DH Group</dt>
              <dd class="text-sm text-gray-900">Group {{ formData.ike_dh_group }}</dd>
            </div>
            <div class="flex py-1.5">
              <dt class="w-40 flex-shrink-0 text-sm font-medium text-gray-500">Lifetime</dt>
              <dd class="text-sm text-gray-900">{{ formData.ike_lifetime }}s</dd>
            </div>
            <div class="flex py-1.5">
              <dt class="w-40 flex-shrink-0 text-sm font-medium text-gray-500">DPD</dt>
              <dd class="text-sm text-gray-900">{{ formData.dpd_enabled ? 'Enabled' : 'Disabled' }}</dd>
            </div>
          </div>
          <div>
            <h4 class="mb-2 text-sm font-semibold text-gray-700">IPsec Phase 2</h4>
            <div class="flex py-1.5">
              <dt class="w-40 flex-shrink-0 text-sm font-medium text-gray-500">Encryption</dt>
              <dd class="text-sm text-gray-900">{{ formData.ipsec_encryption?.toUpperCase() || '---' }}</dd>
            </div>
            <div class="flex py-1.5">
              <dt class="w-40 flex-shrink-0 text-sm font-medium text-gray-500">Integrity</dt>
              <dd class="text-sm text-gray-900">{{ formData.ipsec_integrity?.toUpperCase() || '---' }}</dd>
            </div>
            <div class="flex py-1.5">
              <dt class="w-40 flex-shrink-0 text-sm font-medium text-gray-500">PFS Group</dt>
              <dd class="text-sm text-gray-900">{{ formData.ipsec_pfs_group === 'none' ? 'None' : `Group ${formData.ipsec_pfs_group}` }}</dd>
            </div>
            <div class="flex py-1.5">
              <dt class="w-40 flex-shrink-0 text-sm font-medium text-gray-500">Lifetime</dt>
              <dd class="text-sm text-gray-900">{{ formData.ipsec_lifetime }}s</dd>
            </div>
            <div class="flex py-1.5">
              <dt class="w-40 flex-shrink-0 text-sm font-medium text-gray-500">Tunnel Mode</dt>
              <dd class="text-sm text-gray-900">{{ formData.tunnel_mode === 'tunnel' ? 'Tunnel' : 'Transport' }}</dd>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Routing Section -->
    <div class="rounded-lg border border-gray-200 bg-white">
      <div class="flex items-center justify-between border-b border-gray-200 px-6 py-4">
        <h3 class="text-base font-semibold text-gray-900">Routing & NAT</h3>
        <button type="button" class="text-sm font-medium text-indigo-600 hover:text-indigo-500" @click="goToStep(5)">Edit</button>
      </div>
      <div class="px-6 py-4">
        <div class="flex py-1.5">
          <dt class="w-40 flex-shrink-0 text-sm font-medium text-gray-500">Routing Type</dt>
          <dd class="text-sm text-gray-900">{{ formData.routing_type === 'bgp' ? 'BGP' : 'Static' }}</dd>
        </div>
        <template v-if="formData.routing_type === 'bgp'">
          <div class="flex py-1.5">
            <dt class="w-40 flex-shrink-0 text-sm font-medium text-gray-500">Vendor EP1 ASN</dt>
            <dd class="text-sm text-gray-900">{{ formData.bgp_remote_asn || '---' }}</dd>
          </div>
          <div v-if="formData.vendor_endpoints_count === 2" class="flex py-1.5">
            <dt class="w-40 flex-shrink-0 text-sm font-medium text-gray-500">Vendor EP2 ASN</dt>
            <dd class="text-sm text-gray-900">{{ formData.bgp_remote_asn_2 || formData.bgp_remote_asn || '---' }}</dd>
          </div>
          <div class="flex py-1.5">
            <dt class="w-40 flex-shrink-0 text-sm font-medium text-gray-500">Tunnel IP Assignment</dt>
            <dd class="text-sm text-gray-900">{{ tunnelIpLabel }}</dd>
          </div>
          <div class="flex py-1.5">
            <dt class="w-40 flex-shrink-0 text-sm font-medium text-gray-500">BGP Auth</dt>
            <dd class="text-sm text-gray-900">{{ formData.bgp_auth_enabled ? 'Enabled' : 'Disabled' }}</dd>
          </div>
        </template>
        <template v-if="formData.routing_type === 'static'">
          <div class="flex py-1.5">
            <dt class="w-40 flex-shrink-0 text-sm font-medium text-gray-500">Vendor CIDRs</dt>
            <dd class="text-sm text-gray-900 whitespace-pre-line">{{ formData.vendor_cidrs || 'Not specified' }}</dd>
          </div>
        </template>
        <div class="flex py-1.5">
          <dt class="w-40 flex-shrink-0 text-sm font-medium text-gray-500">NAT Supported</dt>
          <dd class="text-sm text-gray-900">{{ natLabel }}</dd>
        </div>
        <div v-if="formData.nat_supported === false" class="flex py-1.5">
          <dt class="w-40 flex-shrink-0 text-sm font-medium text-gray-500">Exception Reason</dt>
          <dd class="text-sm text-gray-900">{{ formData.nat_exception_reason || '---' }}</dd>
        </div>
      </div>
    </div>

    <!-- Flows Section -->
    <div class="rounded-lg border border-gray-200 bg-white">
      <div class="flex items-center justify-between border-b border-gray-200 px-6 py-4">
        <h3 class="text-base font-semibold text-gray-900">Traffic Flows</h3>
        <button type="button" class="text-sm font-medium text-indigo-600 hover:text-indigo-500" @click="goToStep(6)">Edit</button>
      </div>
      <div class="px-6 py-4">
        <FlowDiagram v-if="requestId" :request-id="requestId" />
        <p v-else class="text-sm text-gray-500">Save the request first to add traffic flows.</p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useWizardState } from '../../composables/useWizardState.js'
import TopologyDiagram from '../shared/TopologyDiagram.vue'
import FlowDiagram from '../shared/FlowDiagram.vue'

const props = defineProps({
  sites: {
    type: Array,
    default: () => [],
  },
  applications: {
    type: Array,
    default: () => [],
  },
})

const { formData, errors, goToStep, requestId } = useWizardState()

const directionalityLabels = {
  we_initiate: 'We Initiate',
  vendor_initiates: 'Vendor Initiates',
  both: 'Both Can Initiate',
}
const directionalityLabel = computed(() => directionalityLabels[formData.directionality] || formData.directionality || 'Not set')

const classificationLabels = {
  public: 'Public',
  internal: 'Internal',
  confidential: 'Confidential',
  restricted: 'Restricted',
}
const classificationLabel = computed(() => classificationLabels[formData.data_classification] || formData.data_classification || 'Not set')

const topologyLabels = {
  bow_tie: 'Bow Tie',
  matched_pairs: 'Matched Pairs',
}
const topologyLabel = computed(() => topologyLabels[formData.topology_type] || formData.topology_type || 'Not set')

const applicationNames = computed(() => {
  if (!formData.application_ids || formData.application_ids.length === 0) return 'None selected'
  const names = formData.application_ids
    .map((id) => {
      const app = props.applications.find((a) => a.id === id)
      return app ? app.name : `ID:${id}`
    })
  return names.join(', ')
})

const site1Name = computed(() => {
  const site = props.sites.find((s) => s.id === formData.our_endpoint_1_site_id)
  return site ? `${site.name} (${site.code})` : ''
})

const site2Name = computed(() => {
  const site = props.sites.find((s) => s.id === formData.our_endpoint_2_site_id)
  return site ? `${site.name} (${site.code})` : ''
})

const tunnelIpLabels = {
  we_assign: 'We assign from tunnel IP pool',
  vendor_assigns: 'Vendor assigns',
  mutual: 'Mutually agreed',
  apipa: 'APIPA (169.254.x.x)',
}
const tunnelIpLabel = computed(() => tunnelIpLabels[formData.tunnel_ip_assignment] || formData.tunnel_ip_assignment || 'Not set')

const natLabel = computed(() => {
  if (formData.nat_supported === true) return 'Yes'
  if (formData.nat_supported === false) return 'No'
  return 'Not Sure'
})
</script>
