import { getSystemInfo } from '~/shared/api/generated/sdk.gen'
import type { SystemInfoResponse } from '~/shared/api/generated/types.gen'
import { configureApiClient } from '~/shared/api/runtime'
import { ref, type Ref } from 'vue'

export type SystemInfoState = {
  data: Ref<SystemInfoResponse | null>
  error: Ref<string | null>
  loading: Ref<boolean>
  load: () => Promise<void>
}

export function useSystemInfo(): SystemInfoState {
  const config = useRuntimeConfig()
  configureApiClient(config.public.apiBaseUrl)

  const data = ref<SystemInfoResponse | null>(null)
  const error = ref<string | null>(null)
  const loading = ref(false)

  async function load() {
    loading.value = true
    error.value = null

    try {
      const response = await getSystemInfo()
      if (response.error) {
        error.value = 'Backend system information is unavailable.'
        data.value = null
        return
      }
      data.value = response.data ?? null
    } catch {
      error.value = 'Backend system information is unavailable.'
      data.value = null
    } finally {
      loading.value = false
    }
  }

  return {
    data,
    error,
    loading,
    load
  }
}
