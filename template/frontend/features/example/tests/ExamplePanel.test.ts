import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import ExamplePanel from '../components/ExamplePanel.vue'

describe('ExamplePanel', () => {
  it('renders the ready state', () => {
    const wrapper = mount(ExamplePanel)
    expect(wrapper.text()).toContain('Ready')
  })
})
