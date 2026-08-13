import { mount } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'

import SystemInfoPanel from '../components/SystemInfoPanel.vue'

const getSystemInfo = vi.fn()

vi.mock('~/shared/api/generated/sdk.gen', () => ({
  getSystemInfo: () => getSystemInfo()
}))

vi.mock('~/shared/api/runtime', () => ({
  configureApiClient: vi.fn()
}))

vi.stubGlobal('useRuntimeConfig', () => ({
  public: {
    apiBaseUrl: 'http://127.0.0.1:8000'
  }
}))

afterEach(() => {
  getSystemInfo.mockReset()
})

describe('SystemInfoPanel', () => {
  it('renders the loading state', async () => {
    getSystemInfo.mockReturnValue(new Promise(() => {}))

    const wrapper = mount(SystemInfoPanel)
    await wrapper.vm.$nextTick()

    expect(wrapper.text()).toContain('Loading system information...')
  })

  it('renders backend system information', async () => {
    getSystemInfo.mockResolvedValue({
      data: {
        name: 'Example Fullstack',
        version: '0.1.0',
        environment: 'local',
        next_step: 'Open project/brief.md'
      },
      error: undefined
    })

    const wrapper = mount(SystemInfoPanel)
    await vi.waitFor(() => expect(wrapper.text()).toContain('Example Fullstack'))

    expect(wrapper.text()).toContain('0.1.0')
    expect(wrapper.text()).toContain('local')
    expect(wrapper.text()).toContain('Open project/brief.md')
    expect(wrapper.text()).not.toContain('Backend system information is unavailable.')
  })

  it('renders API errors', async () => {
    getSystemInfo.mockResolvedValue({
      data: undefined,
      error: { detail: 'unavailable' }
    })

    const wrapper = mount(SystemInfoPanel)
    await vi.waitFor(() =>
      expect(wrapper.text()).toContain('Backend system information is unavailable.')
    )
  })
})
