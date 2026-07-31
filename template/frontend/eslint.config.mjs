import withNuxt from './.nuxt/eslint.config.mjs'

export default withNuxt({
  ignores: [
    '.nuxt/**',
    '.output/**',
    'coverage/**',
    'node_modules/**'
  ]
})
