import { createRouter, createWebHashHistory } from 'vue-router'
import Workbench from './views/Workbench.vue'
import Doctor from './views/Doctor.vue'
import Voices from './views/Voices.vue'
import Training from './views/Training.vue'
import History from './views/History.vue'
import Models from './views/Models.vue'
import Assets from './views/Assets.vue'
import Settings from './views/Settings.vue'
import Datasets from './views/Datasets.vue'
import Preprocess from './views/Preprocess.vue'
import Tasks from './views/Tasks.vue'

export const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    { path: '/', name: 'inference', component: Workbench },
    { path: '/datasets', name: 'datasets', component: Datasets },
    { path: '/preprocess', name: 'preprocess', component: Preprocess },
    { path: '/training', name: 'training', component: Training },
    { path: '/tasks', name: 'tasks', component: Tasks },
    { path: '/voices', name: 'voices', component: Voices },
    { path: '/doctor', name: 'doctor', component: Doctor },
    { path: '/history', name: 'history', component: History },
    { path: '/models', name: 'models', component: Models },
    { path: '/assets', name: 'assets', component: Assets },
    { path: '/settings', name: 'settings', component: Settings },
  ],
})
