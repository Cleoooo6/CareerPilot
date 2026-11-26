import { createApp } from 'vue'

import App from './App.vue'
import { router } from './router'
import { authStore } from './stores/auth'
import './styles/main.css'

if (typeof window !== 'undefined') {
  window.addEventListener('careerpilot:unauthorized', () => {
    authStore.clear()
    const current = router.currentRoute.value
    if (current.name !== 'login' && current.name !== 'register') {
      void router.push({ name: 'login', query: { redirect: current.fullPath } })
    }
  })
}

createApp(App).use(router).mount('#app')