import './assets/main.css'

import { createPinia } from 'pinia'
import { createApp } from 'vue'

import App from './App.vue'
import { router } from './router'

createApp(App).use(createPinia()).use(router).mount('#app')

// PWA (SPEC §15): the service worker only makes the site installable. It is
// registered in production builds only, so that Vite's dev server is never
// behind a worker.
if (import.meta.env.PROD && 'serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/sw.js').catch(() => {
      /* not installable here (private mode, old browser): nothing to do */
    })
  })
}
