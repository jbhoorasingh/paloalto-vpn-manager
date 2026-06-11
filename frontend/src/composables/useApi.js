import { ref } from 'vue'
import { getCsrfToken } from './useCsrf.js'

export function useApi() {
  const loading = ref(false)
  const error = ref(null)

  async function apiFetch(url, options = {}) {
    loading.value = true
    error.value = null

    const defaults = {
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': getCsrfToken(),
      },
      credentials: 'same-origin',
    }

    const merged = {
      ...defaults,
      ...options,
      headers: { ...defaults.headers, ...options.headers },
    }

    try {
      const response = await fetch(url, merged)
      const data = await response.json()

      if (!response.ok) {
        error.value = data.error || data.errors || 'Request failed'
        return { ok: false, data, status: response.status }
      }

      return { ok: true, data, status: response.status }
    } catch (err) {
      error.value = err.message
      return { ok: false, data: null, status: 0 }
    } finally {
      loading.value = false
    }
  }

  return { apiFetch, loading, error }
}
