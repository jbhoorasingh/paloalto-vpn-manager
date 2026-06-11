import { reactive, ref, provide, inject, computed } from 'vue'

const WIZARD_KEY = Symbol('wizard-state')

const STEPS = [
  { id: 1, name: 'Vendor', key: 'vendor' },
  { id: 2, name: 'Apps & Data', key: 'appsData' },
  { id: 3, name: 'Topology', key: 'topology' },
  { id: 4, name: 'Crypto', key: 'crypto' },
  { id: 5, name: 'Routing', key: 'routing' },
  { id: 6, name: 'Flows', key: 'flows' },
  { id: 7, name: 'Review', key: 'review' },
]

export function createWizardState(initialData = {}) {
  const currentStep = ref(1)
  const requestId = ref(initialData.id || null)
  const saving = ref(false)
  const errors = ref({})

  const formData = reactive({
    // Step 1: Vendor
    vendor_id: initialData.vendor_id || null,
    vendor_name: initialData.vendor_name || '',

    // Step 2: Apps & Data
    title: initialData.title || '',
    purpose: initialData.purpose || '',
    application_ids: initialData.application_ids || [],
    directionality: initialData.directionality || '',
    data_description: initialData.data_description || '',
    data_classification: initialData.data_classification || '',

    // Step 3: Topology
    vendor_endpoints_count: initialData.vendor_endpoints_count || 1,
    topology_type: initialData.topology_type || '',
    vendor_endpoint_1_ip: initialData.vendor_endpoint_1_ip || '',
    vendor_endpoint_2_ip: initialData.vendor_endpoint_2_ip || '',
    our_endpoint_1_site_id: initialData.our_endpoint_1_site_id || null,
    our_endpoint_2_site_id: initialData.our_endpoint_2_site_id || null,

    // Step 4: Crypto - IKE
    ike_version: initialData.ike_version || '2',
    auth_method: initialData.auth_method || 'psk',
    ike_encryption: initialData.ike_encryption || 'aes-256-cbc',
    ike_integrity: initialData.ike_integrity || 'sha256',
    ike_dh_group: initialData.ike_dh_group || '14',
    ike_lifetime: initialData.ike_lifetime || 28800,
    dpd_enabled: initialData.dpd_enabled ?? true,
    // Step 4: Crypto - IPsec
    ipsec_encryption: initialData.ipsec_encryption || 'aes-256-gcm',
    ipsec_integrity: initialData.ipsec_integrity || 'sha256',
    ipsec_pfs_group: initialData.ipsec_pfs_group || '14',
    ipsec_lifetime: initialData.ipsec_lifetime || 3600,
    tunnel_mode: initialData.tunnel_mode || 'tunnel',

    // Step 5: Routing
    routing_type: initialData.routing_type || 'static',
    vendor_cidrs: initialData.vendor_cidrs || '',
    bgp_local_asn: initialData.bgp_local_asn || '',
    bgp_remote_asn: initialData.bgp_remote_asn || '',
    bgp_remote_asn_2: initialData.bgp_remote_asn_2 || '',
    bgp_peer_ip_local: initialData.bgp_peer_ip_local || '',
    bgp_peer_ip_remote: initialData.bgp_peer_ip_remote || '',
    bgp_auth_enabled: initialData.bgp_auth_enabled || false,
    tunnel_ip_assignment: initialData.tunnel_ip_assignment || 'we_assign',
    mutual_tunnel_ips: initialData.mutual_tunnel_ips || '[]',
    nat_supported: initialData.nat_supported ?? null,
    nat_exception_reason: initialData.nat_exception_reason || '',
  })

  const isFirstStep = computed(() => currentStep.value === 1)
  const isLastStep = computed(() => currentStep.value === STEPS.length)
  const currentStepInfo = computed(() => STEPS[currentStep.value - 1])

  function nextStep() {
    if (currentStep.value < STEPS.length) {
      currentStep.value++
    }
  }

  function prevStep() {
    if (currentStep.value > 1) {
      currentStep.value--
    }
  }

  function goToStep(step) {
    if (step >= 1 && step <= STEPS.length) {
      currentStep.value = step
    }
  }

  const state = {
    STEPS,
    currentStep,
    requestId,
    saving,
    errors,
    formData,
    isFirstStep,
    isLastStep,
    currentStepInfo,
    nextStep,
    prevStep,
    goToStep,
  }

  provide(WIZARD_KEY, state)
  return state
}

export function useWizardState() {
  const state = inject(WIZARD_KEY)
  if (!state) {
    throw new Error('useWizardState must be used within a wizard provider')
  }
  return state
}
