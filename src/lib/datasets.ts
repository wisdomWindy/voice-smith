import { ref } from 'vue'

export type DatasetRecord = {
  id: string
  name: string
  rawAudio: string
  createdAt: string
  status: 'raw' | 'preprocessed'
  listPath?: string
  slicesDir?: string
}

const KEY = 'voicesmith.datasets.v1'

function load(): DatasetRecord[] {
  try {
    return JSON.parse(localStorage.getItem(KEY) || '[]') as DatasetRecord[]
  } catch {
    return []
  }
}

export const datasets = ref<DatasetRecord[]>(load())

export function saveDatasets() {
  localStorage.setItem(KEY, JSON.stringify(datasets.value))
}

export function addDataset(name: string, rawAudio: string): DatasetRecord {
  const record: DatasetRecord = {
    id: `ds_${Date.now().toString(36)}`,
    name: name.trim() || `数据集 ${datasets.value.length + 1}`,
    rawAudio,
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
