import { computed, ref } from 'vue'

export type Project = {
  id: string
  name: string
  path: string
  createdAt: string
}

const KEY = 'voicesmith.projects.v1'
const SELECTED_KEY = 'voicesmith.selected-project.v1'

function loadProjects(): Project[] {
  try {
    return JSON.parse(localStorage.getItem(KEY) || '[]') as Project[]
  } catch {
    return []
  }
}

export const projects = ref<Project[]>(loadProjects())
export const selectedProjectId = ref<string>(localStorage.getItem(SELECTED_KEY) || '')
export const selectedProject = computed(() => projects.value.find((item) => item.id === selectedProjectId.value) || null)

export function persistProjects() {
  localStorage.setItem(KEY, JSON.stringify(projects.value))
  localStorage.setItem(SELECTED_KEY, selectedProjectId.value)
}

export function addProject(path: string): Project {
  const normalized = path.replace(/[\\/]+$/, '')
  const name = normalized.split(/[\\/]/).pop() || normalized
  const existing = projects.value.find((item) => item.path.toLowerCase() === normalized.toLowerCase())
  if (existing) {
    selectedProjectId.value = existing.id
    persistProjects()
    return existing
  }
  const project: Project = {
    id: `proj_${Date.now().toString(36)}`,
    name,
    path: normalized,
    createdAt: new Date().toISOString(),
  }
  projects.value = [project, ...projects.value]
  selectedProjectId.value = project.id
  persistProjects()
  return project
}

export function selectProject(id: string) {
  selectedProjectId.value = id
  persistProjects()
}

export function removeProject(id: string) {
  projects.value = projects.value.filter((item) => item.id !== id)
  if (selectedProjectId.value === id) selectedProjectId.value = projects.value[0]?.id || ''
  persistProjects()
}
