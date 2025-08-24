// https://nuxt.com/docs/api/configuration/nuxt-config
import tailwindcss from "@tailwindcss/vite";
export default defineNuxtConfig({
  compatibilityDate: '2025-07-15',
  devtools: { enabled: true },
  css : ['assets/css/main.css'],
  vite: {
    plugins: [tailwindcss(),],
  },
  runtimeConfig: {
    apiUrl : process.env.API_URL
  },
  routeRules: {
    // forward semua /api/** ke <apiUrl>/api/**
    '/api/**': { proxy: { to: `${process.env.NUXT_API_URL}/api/**` } },
  },
})
