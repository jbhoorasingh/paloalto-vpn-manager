<template>
  <div class="space-y-6">
    <div>
      <h2 class="text-xl font-semibold text-gray-900">Cryptographic Settings</h2>
      <p class="mt-1 text-sm text-gray-500">Configure IKE Phase 1 and IPsec Phase 2 parameters.</p>
    </div>

    <!-- Preset buttons -->
    <div class="flex gap-3">
      <button
        type="button"
        class="inline-flex items-center rounded-md border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 shadow-sm hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2"
        @click="applyPreset('standard')"
      >
        <svg class="mr-2 h-4 w-4 text-blue-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
        </svg>
        Standard Preset
      </button>
      <button
        type="button"
        class="inline-flex items-center rounded-md border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 shadow-sm hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2"
        @click="applyPreset('high')"
      >
        <svg class="mr-2 h-4 w-4 text-green-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
        </svg>
        High Security Preset
      </button>
    </div>

    <!-- IKE Phase 1 Section -->
    <div class="rounded-lg border border-gray-200 bg-white p-6">
      <h3 class="mb-4 text-lg font-medium text-gray-900">IKE Phase 1</h3>
      <div class="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <!-- IKE Version -->
        <div>
          <label for="ike_version" class="block text-sm font-medium text-gray-700">IKE Version</label>
          <select
            id="ike_version"
            v-model="formData.ike_version"
            class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
          >
            <option value="1">IKEv1</option>
            <option value="2">IKEv2</option>
          </select>
        </div>

        <!-- Auth Method -->
        <div>
          <label for="auth_method" class="block text-sm font-medium text-gray-700">Authentication Method</label>
          <select
            id="auth_method"
            v-model="formData.auth_method"
            class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
          >
            <option value="psk">Pre-Shared Key (PSK)</option>
            <option value="certificate">Certificate</option>
          </select>
        </div>

        <!-- IKE Encryption -->
        <div>
          <label for="ike_encryption" class="block text-sm font-medium text-gray-700">Encryption</label>
          <select
            id="ike_encryption"
            v-model="formData.ike_encryption"
            class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
          >
            <option value="aes-128-cbc">AES-128-CBC</option>
            <option value="aes-256-cbc">AES-256-CBC</option>
            <option value="aes-128-gcm">AES-128-GCM</option>
            <option value="aes-256-gcm">AES-256-GCM</option>
          </select>
        </div>

        <!-- IKE Integrity -->
        <div>
          <label for="ike_integrity" class="block text-sm font-medium text-gray-700">Integrity</label>
          <select
            id="ike_integrity"
            v-model="formData.ike_integrity"
            class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
          >
            <option value="sha1">SHA-1</option>
            <option value="sha256">SHA-256</option>
            <option value="sha384">SHA-384</option>
            <option value="sha512">SHA-512</option>
          </select>
        </div>

        <!-- DH Group -->
        <div>
          <label for="ike_dh_group" class="block text-sm font-medium text-gray-700">DH Group</label>
          <select
            id="ike_dh_group"
            v-model="formData.ike_dh_group"
            class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
          >
            <option value="2">Group 2 (1024-bit)</option>
            <option value="5">Group 5 (1536-bit)</option>
            <option value="14">Group 14 (2048-bit)</option>
            <option value="19">Group 19 (256-bit ECP)</option>
            <option value="20">Group 20 (384-bit ECP)</option>
            <option value="21">Group 21 (521-bit ECP)</option>
          </select>
        </div>

        <!-- IKE Lifetime -->
        <div>
          <label for="ike_lifetime" class="block text-sm font-medium text-gray-700">Lifetime (seconds)</label>
          <input
            id="ike_lifetime"
            v-model.number="formData.ike_lifetime"
            type="number"
            min="3600"
            max="86400"
            class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
          />
          <p class="mt-1 text-xs text-gray-500">{{ formatDuration(formData.ike_lifetime) }}</p>
        </div>

        <!-- DPD -->
        <div class="sm:col-span-2 lg:col-span-3">
          <label class="flex items-center">
            <input
              type="checkbox"
              v-model="formData.dpd_enabled"
              class="h-4 w-4 rounded border-gray-300 text-indigo-600 focus:ring-indigo-500"
            />
            <span class="ml-2 text-sm text-gray-700">Dead Peer Detection (DPD) Enabled</span>
          </label>
        </div>
      </div>
    </div>

    <!-- IPsec Phase 2 Section -->
    <div class="rounded-lg border border-gray-200 bg-white p-6">
      <h3 class="mb-4 text-lg font-medium text-gray-900">IPsec Phase 2</h3>
      <div class="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <!-- IPsec Encryption -->
        <div>
          <label for="ipsec_encryption" class="block text-sm font-medium text-gray-700">Encryption</label>
          <select
            id="ipsec_encryption"
            v-model="formData.ipsec_encryption"
            class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
          >
            <option value="aes-128-cbc">AES-128-CBC</option>
            <option value="aes-256-cbc">AES-256-CBC</option>
            <option value="aes-128-gcm">AES-128-GCM</option>
            <option value="aes-256-gcm">AES-256-GCM</option>
          </select>
        </div>

        <!-- IPsec Integrity -->
        <div>
          <label for="ipsec_integrity" class="block text-sm font-medium text-gray-700">Integrity</label>
          <select
            id="ipsec_integrity"
            v-model="formData.ipsec_integrity"
            class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
          >
            <option value="sha1">SHA-1</option>
            <option value="sha256">SHA-256</option>
            <option value="sha384">SHA-384</option>
            <option value="sha512">SHA-512</option>
          </select>
        </div>

        <!-- PFS Group -->
        <div>
          <label for="ipsec_pfs_group" class="block text-sm font-medium text-gray-700">PFS Group</label>
          <select
            id="ipsec_pfs_group"
            v-model="formData.ipsec_pfs_group"
            class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
          >
            <option value="none">None</option>
            <option value="2">Group 2 (1024-bit)</option>
            <option value="5">Group 5 (1536-bit)</option>
            <option value="14">Group 14 (2048-bit)</option>
            <option value="19">Group 19 (256-bit ECP)</option>
            <option value="20">Group 20 (384-bit ECP)</option>
            <option value="21">Group 21 (521-bit ECP)</option>
          </select>
        </div>

        <!-- IPsec Lifetime -->
        <div>
          <label for="ipsec_lifetime" class="block text-sm font-medium text-gray-700">Lifetime (seconds)</label>
          <input
            id="ipsec_lifetime"
            v-model.number="formData.ipsec_lifetime"
            type="number"
            min="900"
            max="28800"
            class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
          />
          <p class="mt-1 text-xs text-gray-500">{{ formatDuration(formData.ipsec_lifetime) }}</p>
        </div>

        <!-- Tunnel Mode -->
        <div>
          <label for="tunnel_mode" class="block text-sm font-medium text-gray-700">Tunnel Mode</label>
          <select
            id="tunnel_mode"
            v-model="formData.tunnel_mode"
            class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
          >
            <option value="tunnel">Tunnel Mode</option>
            <option value="transport">Transport Mode</option>
          </select>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { useWizardState } from '../../composables/useWizardState.js'

const { formData } = useWizardState()

const presets = {
  standard: {
    ike_version: '2',
    auth_method: 'psk',
    ike_encryption: 'aes-256-cbc',
    ike_integrity: 'sha256',
    ike_dh_group: '14',
    ike_lifetime: 28800,
    dpd_enabled: true,
    ipsec_encryption: 'aes-256-gcm',
    ipsec_integrity: 'sha256',
    ipsec_pfs_group: '14',
    ipsec_lifetime: 3600,
    tunnel_mode: 'tunnel',
  },
  high: {
    ike_version: '2',
    auth_method: 'certificate',
    ike_encryption: 'aes-256-gcm',
    ike_integrity: 'sha512',
    ike_dh_group: '20',
    ike_lifetime: 14400,
    dpd_enabled: true,
    ipsec_encryption: 'aes-256-gcm',
    ipsec_integrity: 'sha512',
    ipsec_pfs_group: '20',
    ipsec_lifetime: 1800,
    tunnel_mode: 'tunnel',
  },
}

function applyPreset(name) {
  const preset = presets[name]
  if (!preset) return
  Object.assign(formData, preset)
}

function formatDuration(seconds) {
  if (!seconds || seconds <= 0) return ''
  const hours = Math.floor(seconds / 3600)
  const mins = Math.floor((seconds % 3600) / 60)
  const parts = []
  if (hours > 0) parts.push(`${hours}h`)
  if (mins > 0) parts.push(`${mins}m`)
  return parts.join(' ') || '< 1m'
}
</script>
