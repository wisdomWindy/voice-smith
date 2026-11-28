import { useEngineStore } from '../stores/engine'
import { datasets, updateDataset } from './datasets'

/**
 * Applies finished preprocess tasks to the local dataset records. The watcher
 * lives at app level so a task keeps updating its dataset even after the user
 * navigates away from the preprocess page.
 */
let timer: number | undefined

export function startTaskWatcher(): void {
  if (timer) return
  const engine = useEngineStore()

  async function tick() {
    if (!engine.client || engine.status !== 'ready') return
    try {
      const tasks = await engine.client.tasks(50)
      for (const task of tasks) {
        if (task.kind !== 'preprocess' || task.status !== 'succeeded') continue
        const payload = task.payload as { dataset_id?: string } | undefined
        const result = task.result as { list_path?: string; slices_dir?: string } | undefined
        if (!payload?.dataset_id || !result?.list_path) continue
        const dataset = datasets.value.find((item) => item.id === payload.dataset_id)
        if (!dataset) continue
        if (dataset.status === 'preprocessed' && dataset.listPath === result.list_path) continue
        updateDataset(dataset.id, {
          status: 'preprocessed',
          listPath: result.list_path,
          slicesDir: result.slices_dir,
        })
      }
    } catch {
      // The engine may be restarting; the next tick retries.
    }
  }

  timer = window.setInterval(() => void tick(), 4000)
  void tick()
}
