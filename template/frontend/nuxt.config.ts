export default defineNuxtConfig({
  modules: ['@nuxt/eslint'],
  devtools: { enabled: false },
  routeRules: {
    '/**': {
      headers: {
        'X-Content-Type-Options': 'nosniff',
        'Referrer-Policy': 'strict-origin-when-cross-origin',
        'Content-Security-Policy': "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self' http://127.0.0.1:* http://localhost:*; object-src 'none'; base-uri 'self'; frame-ancestors 'none'"
      }
    }
  },
  runtimeConfig: {
    public: {
      apiBaseUrl: process.env.NUXT_PUBLIC_API_BASE_URL || 'http://127.0.0.1:8000'
    }
  },
  typescript: {
    strict: true
  }
})
