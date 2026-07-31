import { defineConfig } from '@hey-api/openapi-ts'

export default defineConfig({
  input: '../artifacts/openapi.json',
  output: process.env.OPENAPI_CLIENT_OUTPUT || 'shared/api/generated'
})
