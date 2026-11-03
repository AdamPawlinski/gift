// https://nuxt.com/docs/api/configuration/nuxt-config
export default defineNuxtConfig({
  ssr: false,
  devtools: { enabled: true },
  modules: ['@nuxt/ui'],
  colorMode: { preference: 'light' },

  runtimeConfig: {
    public: {
      supabaseUrl: '',
      supabaseAnonKey: '',
      apiBase: 'http://localhost:8000/api'
    }
  },

  compatibilityDate: '2026-11-02'
})