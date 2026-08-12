import type { WelcomeContent } from '../types/welcome'

export type NormalizedWelcomeContent = {
  projectName: string
  description: string
  nextStepHref: string
  nextStepLabel: string
}

export function normalizeWelcomeContent(content: WelcomeContent): NormalizedWelcomeContent {
  const projectName = content.projectName.trim()
  const description = content.description.trim()

  if (!projectName) {
    throw new Error('Welcome content requires a project name.')
  }

  return {
    projectName,
    description: description || 'Start by reviewing the generated project brief.',
    nextStepHref: content.nextStepHref?.trim() || '/project/brief.md',
    nextStepLabel: content.nextStepLabel?.trim() || 'Open project/brief.md'
  }
}
