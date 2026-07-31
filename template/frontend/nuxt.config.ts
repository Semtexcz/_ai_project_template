export default defineNuxtConfig({
  modules: ['@unocss/nuxt'],
  devtools: { enabled: true },
  typescript: {
    strict: true
  },
  runtimeConfig: {
    public: {
      apiBase: process.env.NUXT_PUBLIC_API_BASE ?? 'http://localhost:8000'
    }
  }
})
