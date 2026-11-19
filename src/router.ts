import { createRouter, createWebHashHistory } from 'vue-router'
import Workbench from './views/Workbench.vue'
import Doctor from './views/Doctor.vue'
import Voices from './views/Voices.vue'
import Training from './views/Training.vue'
import History from './views/History.vue'
import Models from './views/Models.vue'
import Assets from './views/Assets.vue'
import Settings from './views/Settings.vue'

export const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    { path: '/', name: 'workbench', component: Workbench },
    { path: '/doctor', name: 'doctor', component: Doctor },
    { path: '/voices', name: 'voices', component: Voices },
    { path: '/training', name: 'training', component: Training },
    { path: '/history', name: 'history', component: History },
    { path: '/models', name: 'models', component: Models },
    { path: '/assets', name: 'assets', component: Assets },
    { path: '/settings', name: 'settings', component: Settings },
  ],
})
