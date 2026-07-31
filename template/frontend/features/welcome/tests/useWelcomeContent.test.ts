import { describe, expect, it } from 'vitest'

import { normalizeWelcomeContent } from '../composables/useWelcomeContent'

describe('normalizeWelcomeContent', () => {
  it('normalizes optional next-step content', () => {
    expect(
      normalizeWelcomeContent({
        projectName: ' Example Frontend ',
        description: ' Ready to build. '
      })
    ).toEqual({
      projectName: 'Example Frontend',
      description: 'Ready to build.',
      nextStepHref: '/project/index.md',
      nextStepLabel: 'Open project/index.md'
    })
  })

  it('rejects an empty project name', () => {
    expect(() =>
      normalizeWelcomeContent({
        projectName: '   ',
        description: 'Ready'
      })
    ).toThrow('project name')
  })
})
