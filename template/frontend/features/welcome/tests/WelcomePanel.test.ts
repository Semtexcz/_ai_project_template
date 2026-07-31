import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import WelcomePanel from '../components/WelcomePanel.vue'

describe('WelcomePanel', () => {
  it('renders the project heading and project index link', () => {
    const wrapper = mount(WelcomePanel, {
      props: {
        content: {
          projectName: 'Example Frontend',
          description: 'Generated frontend project.',
          nextStepHref: '/project/index.md',
          nextStepLabel: 'Open project/index.md to continue.'
        }
      }
    })

    const heading = wrapper.get('h1')
    expect(heading.text()).toBe('Example Frontend')
    expect(wrapper.findAll('h1')).toHaveLength(1)
    expect(wrapper.get('section').attributes('aria-labelledby')).toBe('welcome-title')
    expect(wrapper.get('a').attributes('href')).toBe('/project/index.md')
    expect(wrapper.get('a').text()).toContain('project/index.md')
  })

  it('renders empty-description fallback text', () => {
    const wrapper = mount(WelcomePanel, {
      props: {
        content: {
          projectName: 'Example Frontend',
          description: ''
        }
      }
    })

    expect(wrapper.text()).toContain('Start by reviewing the generated project dashboard.')
  })
})
