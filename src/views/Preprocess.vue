<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useEngineStore } from '../stores/engine'
import { datasets } from '../lib/datasets'
import { selectedProject } from '../lib/projects'
import type { TaskInfo } from '../lib/engine'
import { taskDetail, taskLabel, taskPercent, taskStatusLabel, taskStatusTone } from '../lib/taskView'

const engine = useEngineStore()
const selectedId = ref(datasets.value[0]?.id || '')
const creating = ref(false)
const error = ref('')
const message = ref('')
const tasks = ref<TaskInfo[]>([])
let timer: number | undefined

const visibleDatasets = computed(() => datasets.value.filter((item) => item.projectId === selectedProject.value?.id))
const selected = computed(() => visibleDatasets.value.find((item) => item.id === selectedId.value))
const canRun = computed(() => Boolean(selected.value && engine.client && engine.status === 'ready' && !creating.value))
const recentTasks = computed(() => tasks.value.slice(0, 5))

function isActive(status: string): boolean {
  return ['queued', 'running', 'cancelling'].includes(status)
}

async function loadTasks() {
  if (!engine.client || engine.status !== 'ready') return
  try {
    tasks.value = await engine.client.tasks(20, 'preprocess')
  } catch {
    // The engine may be restarting; the next poll will pick the list up again.
  }
}

async function run() {
  if (!engine.client || !selected.value) return
  if (!selected.value.rawAudios.length) {
    error.value = '数据集没有原始音频'
    return
  }
  creating.value = true
  error.value = ''
  message.value = ''
  try {
    const task = await engine.client.createTask('preprocess', `预处理 · ${selected.value.name}`, {
      dataset_id: selected.value.id,
      dataset_name: selected.value.name,
      audio_paths: [...selected.value.rawAudios],
      language: 'zh',
      speaker: 'speaker',
      min_sec: 5,
    })
    message.value = `已加入队列：${task.title}（切换页面不会中断，可在「任务」页查看进度）`
    await loadTasks()
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  } finally {
    creating.value = false
  }
}

async function cancel(task: TaskInfo) {
  if (!engine.client) return
  try {
    await engine.client.cancelTask(task.id)
    await loadTasks()
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  }
}

onMounted(() => {
  void loadTasks()
  timer = window.setInterval(() => void loadTasks(), 2000)
})

onBeforeUnmount(() => {
  if (timer) window.clearInterval(timer)
})
</script>

<template>
  <section class="page">
    <div class="card">
      <div class="card-head">
        <div>
          <h2>预处理配置</h2>
          <p class="muted small">选择数据集，自动执行 V5 预处理：人声分离、切片、ASR、训练清单。</p>
        </div>
      </div>
      <div v-if="error" class="inline-error">{{ error }}</div>
      <div v-if="message" class="banner success">{{ message }}</div>
      <label class="field">
        <span>数据集</span>
        <select v-model="selectedId" class="input">
          <option v-for="item in visibleDatasets" :key="item.id" :value="item.id">
            {{ item.name }} · {{ item.rawAudios.length }} 个音频 · {{ item.status === 'raw' ? '待预处理' : '已预处理' }}
          </option>
        </select>
      </label>
      <p class="muted small">
        每次点击都会创建一个独立任务，按顺序排队执行；切换页面不会中断。
      </p>
      <button class="button primary" :disabled="!canRun" @click="run">
        {{ creating ? '提交中…' : '开始预处理' }}
      </button>

      <div v-if="recentTasks.length" class="task-list">
        <div v-for="task in recentTasks" :key="task.id" class="task-item">
          <div class="task-main">
            <div class="task-title">
              <span>{{ taskLabel(task) }}</span>
              <span class="tag" :class="taskStatusTone(task.status)">{{ taskStatusLabel(task.status) }}</span>
            </div>
            <div class="muted tiny">{{ taskDetail(task) }}</div>
            <div v-if="isActive(task.status)" class="progress">
              <div class="progress-bar" :style="{ width: `${taskPercent(task.progress)}%` }"></div>
            </div>
          </div>
          <span class="muted small">{{ taskPercent(task.progress) }}%</span>
          <button v-if="isActive(task.status)" class="button ghost small" @click="cancel(task)">取消</button>
        </div>
      </div>
    </div>
  </section>
</template>

<style scoped>
.task-list {
  display: grid;
  gap: 8px;
  margin-top: 16px;
}
.task-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 12px;
  border: 1px solid var(--line-soft);
  border-radius: 9px;
  background: #0f141d;
}
.task-main {
  min-width: 0;
  flex: 1;
  display: grid;
  gap: 4px;
}
.task-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  font-weight: 600;
}
.task-title span:first-child {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.progress {
  width: 100%;
}
</style>
