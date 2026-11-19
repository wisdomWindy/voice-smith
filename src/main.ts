import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import { router } from './router'
import './styles.css'

function showFatal(message: string) {
  const pre = document.createElement('pre')
  pre.style.cssText = 'white-space:pre-wrap;padding:24px;color:#ffb3b3;background:#0c1017;font:13px/1.6 Consolas,monospace;min-height:100vh;margin:0'
  pre.textContent = `VoiceSmith 启动失败\n\n${message}`
  document.body.appendChild(pre)
}

window.addEventListener('error', (event) => {
  showFatal(event.error?.stack || event.message || 'unknown error')
})
window.addEventListener('unhandledrejection', (event) => {
  showFatal(String(event.reason?.stack || event.reason || 'unhandled rejection'))
})

createApp(App).use(createPinia()).use(router).mount('#app')
