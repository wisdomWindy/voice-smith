import { ref } from 'vue'

export type DatasetRecord = {
  id: string
  projectId: string
  name: string
  rawAudios: string[]
  createdAt: string
  status: 'raw' | 'preprocessed'
  listPath?: string
  slicesDir?: string
}

const KEY = 'voicesmith.datasets.v1'

function normalize(item: Partial<DatasetRecord> & { rawAudio?: string }): DatasetRecord {
  const rawAudios = item.rawAudios?.length
    ? item.rawAudios
    : item.rawAudio
      ? [item.rawAudio]
      : []
  return {
    id: item.id || `ds_${crypto.randomUUID()}`,
    projectId: item.projectId || '',
    name: item.name || '数据集',
    rawAudios,
    createdAt: item.createdAt || new Date().toISOString(),
    status: item.status || 'raw',
    listPath: item.listPath,
    slicesDir: item.slicesDir,
  }
}

function load(): DatasetRecord[] {
  try {
    const parsed = JSON.parse(localStorage.getItem(KEY) || '[]') as (Partial<DatasetRecord> & {
      rawAudio?: string
    })[]
    return parsed.map(normalize)
  } catch {
    return []
  }
}

export const datasets = ref<DatasetRecord[]>(load())

export function saveDatasets() {
  localStorage.setItem(KEY, JSON.stringify(datasets.value))
}

export function addDataset(name: string, rawAudios: string[], projectId: string): DatasetRecord {
  const record: DatasetRecord = {
    id: `ds_${crypto.randomUUID()}`,
    projectId,
    name: name.trim() || `数据集 ${datasets.value.length + 1}`,
    rawAudios,
    createdAt: new Date().toISOString(),
    status: 'raw',
  }
  datasets.value = [record, ...datasets.value]
  saveDatasets()
  return record
}

export function updateDataset(id: string, patch: Partial<DatasetRecord>) {
  datasets.value = datasets.value.map((item) => (item.id === id ? { ...item, ...patch } : item))
  saveDatasets()
}

export function deleteDataset(id: string) {
  datasets.value = datasets.value.filter((item) => item.id !== id)
  saveDatasets()
}
