import type { TaskInfo } from './engine'

const STATUS_LABEL: Record<string, string> = {
  queued: '排队中',
  running: '处理中',
  cancelling: '停止中',
  succeeded: '已完成',
  failed: '失败',
  cancelled: '已取消',
}

export function taskStatusLabel(status: string): string {
  return STATUS_LABEL[status] ?? status
}

export function taskStatusTone(status: string): string {
  if (status === 'succeeded') return 'pass'
  if (status === 'failed' || status === 'cancelled') return 'fail'
  if (status === 'queued') return 'queued'
  return 'warn'
}

export function taskPercent(progress: number): number {
  return Math.max(0, Math.min(100, Math.round((progress || 0) * 100)))
}

export function taskKindLabel(kind: string): string {
  return kind === 'preprocess' ? '预处理' : kind
}

export function taskLabel(task: TaskInfo): string {
  const kind = taskKindLabel(task.kind)
  return task.title.startsWith(kind) ? task.title : `${kind} · ${task.title}`
}

export function taskDetail(task: TaskInfo): string {
  if (task.status === 'failed' || task.status === 'cancelled') return task.detail || taskStatusLabel(task.status)
  if (task.status === 'succeeded') {
    const result = task.result as { count?: number; total_duration?: number } | undefined
    if (result?.count) {
      return `完成 · ${result.count} 条 · ${Math.round(result.total_duration || 0)} 秒`
    }
    return '已完成'
  }
  if (task.status === 'queued') return '等待执行'
  return task.detail || task.stage || '处理中'
}
