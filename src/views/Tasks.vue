<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'
import { useEngineStore } from '../stores/engine'
import { isTauri, type Job, type TaskInfo, type Training } from '../lib/engine'
import { datasets } from '../lib/datasets'
import { taskDetail, taskLabel, taskPercent, taskStatusLabel, taskStatusTone } from '../lib/taskView'

const engine = useEngineStore()
const trainings = ref<Training[]>([])
const jobs = ref<Job[]>([])
const tasks = ref<TaskInfo[]>([])
const error = ref('')
let timer: number | undefined

async function load() {
  if (!engine.client) return
  try {
    trainings.value = await engine.client.trainings()
    jobs.value = await engine.client.jobs()
    tasks.value = await engine.client.tasks(20)
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  }
}

async function cancelTraining(item: Training) {
  if (!engine.client) return
  await engine.client.cancelTraining(item.id)
  await load()
}

async function retryTraining(item: Training, force = false) {
  if (!engine.client) return
  await engine.client.createTraining({
    dataset_list: item.dataset_list,
    exp_name: item.exp_name,
    force,
  })
  await load()
}

async function cancelJob(item: Job) {
  if (!engine.client) return
  await engine.client.cancelJob(item.id)
  await load()
}

async function retryJob(item: Job) {
  if (!engine.client || !item.text || !item.voice_id) return
  await engine.client.createSynthesis(item.text, item.voice_id, {})
  await load()
}

async function openFolder(item: Job) {
  if (!item.audio_path || !isTauri()) return
  const { openPath } = await import('@tauri-apps/plugin-opener')
  await openPath(item.audio_path.replace(/[\\/][^\\/]+$/, ''))
}

async function deleteAudio(item: Job) {
  if (!engine.client) return
  if (!window.confirm('删除这条推理记录和对应音频？')) return
  await engine.client.deleteJob(item.id)
  await load()
}

function percent(value: number | undefined): number {
  return Math.max(0, Math.min(100, Math.round(value || 0)))
}

function isActive(status: string) {
  return ['queued', 'running', 'cancelling'].includes(status)
}

async function cancelTask(item: TaskInfo) {
  if (!engine.client) return
  await engine.client.cancelTask(item.id)
  await load()
}

onMounted(() => {
  void load()
  timer = window.setInterval(() => void load(), 3000)
})
onUnmounted(() => {
  if (timer) window.clearInterval(timer)
})
</script>

<template>
  <section class="page">
    <div v-if="error" class="inline-error">{{ error }}</div>

    <div class="card">
      <div class="card-head"><h2>数据集预处理</h2></div>
      <div class="table-wrap">
        <table class="table">
          <thead><tr><th>数据集</th><th>状态</th><th>清单</th></tr></thead>
          <tbody>
            <tr v-for="item in datasets" :key="item.id">
              <td>{{ item.name }}</td>
              <td>{{ item.status === 'preprocessed' ? '已完成' : '待预处理' }}</td>
              <td class="ellipsis">{{ item.listPath || '—' }}</td>
            </tr>
            <tr v-if="!datasets.length"><td colspan="3" class="muted">还没有数据集。</td></tr>
          </tbody>
        </table>
      </div>
    </div>

    <div class="card" style="margin-top:16px">
      <div class="card-head">
        <div>
          <h2>后台任务</h2>
          <p class="muted small">预处理等长任务按顺序排队执行，切换页面不会中断。</p>
        </div>
      </div>
      <div class="table-wrap">
        <table class="table">
          <thead><tr><th>任务</th><th>状态</th><th>进度</th><th>详情</th><th>操作</th></tr></thead>
          <tbody>
            <tr v-for="item in tasks" :key="item.id">
              <td class="ellipsis">{{ taskLabel(item) }}</td>
              <td><span class="tag" :class="taskStatusTone(item.status)">{{ taskStatusLabel(item.status) }}</span></td>
              <td>{{ taskPercent(item.progress) }}%</td>
              <td class="ellipsis">{{ taskDetail(item) }}</td>
              <td><button v-if="isActive(item.status)" class="button ghost small" @click="cancelTask(item)">取消</button></td>
            </tr>
            <tr v-if="!tasks.length"><td colspan="5" class="muted">还没有后台任务。</td></tr>
          </tbody>
        </table>
      </div>
    </div>

    <div class="card" style="margin-top:16px">
      <div class="card-head"><h2>训练任务</h2></div>
      <div class="table-wrap">
        <table class="table">
          <thead><tr><th>实验</th><th>状态</th><th>阶段</th><th>进度</th><th>详情</th><th>操作</th></tr></thead>
          <tbody>
            <tr v-for="item in trainings" :key="item.id">
              <td>{{ item.exp_name }}</td><td>{{ item.status }}</td><td>{{ item.stage }}</td>
              <td>{{ percent(item.progress) }}%</td>
              <td class="ellipsis">{{ item.detail || '—' }}</td>
              <td class="row gap">
                <button v-if="isActive(item.status)" class="button ghost small" @click="cancelTraining(item)">取消</button>
                <button v-if="['failed', 'cancelled'].includes(item.status)" class="button ghost small" @click="retryTraining(item)">重试</button>
                <button v-if="item.status === 'failed'" class="button ghost small" @click="retryTraining(item, true)">强制重试</button>
              </td>
            </tr>
            <tr v-if="!trainings.length"><td colspan="6" class="muted">还没有预处理/训练任务。</td></tr>
          </tbody>
        </table>
      </div>
    </div>

    <div class="card" style="margin-top:16px">
      <div class="card-head"><h2>推理任务</h2></div>
      <div class="table-wrap">
        <table class="table">
          <thead><tr><th>文本</th><th>状态</th><th>进度</th><th>操作</th></tr></thead>
          <tbody>
            <tr v-for="item in jobs" :key="item.id">
              <td class="ellipsis">{{ item.text }}</td>
              <td>{{ item.status }}</td>
              <td>{{ percent(item.progress) }}%</td>
              <td class="row gap">
                <button v-if="isActive(item.status)" class="button ghost small" @click="cancelJob(item)">取消</button>
                <button v-if="['failed', 'cancelled'].includes(item.status)" class="button ghost small" @click="retryJob(item)">重试</button>
                <button v-if="item.status === 'succeeded' && item.audio_path" class="button ghost small" @click="openFolder(item)">打开文件夹</button>
                <button v-if="item.status === 'succeeded' && item.audio_path" class="button ghost small" @click="deleteAudio(item)">删除</button>
              </td>
            </tr>
            <tr v-if="!jobs.length"><td colspan="4" class="muted">还没有推理任务。</td></tr>
          </tbody>
        </table>
      </div>
    </div>
  </section>
</template>
