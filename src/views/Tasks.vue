<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'
import { useEngineStore } from '../stores/engine'
import { isTauri, type Job, type Training } from '../lib/engine'
import { datasets } from '../lib/datasets'

const engine = useEngineStore()
const trainings = ref<Training[]>([])
const jobs = ref<Job[]>([])
const error = ref('')
let timer: number | undefined

async function load() {
  if (!engine.client) return
  try {
    trainings.value = await engine.client.trainings()
    jobs.value = await engine.client.jobs()
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  }
}

async function cancelTraining(item: Training) {
  if (!engine.client) return
  await engine.client.cancelTraining(item.id)
  await load()
}

async function retryTraining(item: Training) {
  if (!engine.client) return
  await engine.client.createTraining({ dataset_list: item.dataset_list, exp_name: item.exp_name })
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
  if (!item.audio_path || !isTauri()) return
  if (!window.confirm('删除这条推理音频？')) return
  const { invoke } = await import('@tauri-apps/api/core')
  await invoke('delete_output', { path: item.audio_path })
  await load()
}

function isActive(status: string) {
  return ['queued', 'running', 'cancelling'].includes(status)
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

    <div class="card" style="margin-top:16px">
      <div class="card-head"><h2>训练任务</h2></div>
      <table class="table">
        <thead><tr><th>实验</th><th>状态</th><th>阶段</th><th>进度</th><th>操作</th></tr></thead>
        <tbody>
          <tr v-for="item in trainings" :key="item.id">
            <td>{{ item.exp_name }}</td><td>{{ item.status }}</td><td>{{ item.stage }}</td>
            <td>{{ Math.round((item.progress || 0) * 100) }}%</td>
            <td class="row gap">
              <button v-if="isActive(item.status)" class="button ghost small" @click="cancelTraining(item)">取消</button>
              <button v-if="['failed', 'cancelled'].includes(item.status)" class="button ghost small" @click="retryTraining(item)">重试</button>
            </td>
          </tr>
          <tr v-if="!trainings.length"><td colspan="5" class="muted">还没有预处理/训练任务。</td></tr>
        </tbody>
      </table>
    </div>

    <div class="card" style="margin-top:16px">
      <div class="card-head"><h2>推理任务</h2></div>
      <table class="table">
        <thead><tr><th>文本</th><th>状态</th><th>进度</th><th>操作</th></tr></thead>
        <tbody>
          <tr v-for="item in jobs" :key="item.id">
            <td class="ellipsis">{{ item.text }}</td>
            <td>{{ item.status }}</td>
            <td>{{ Math.round((item.progress || 0) * 100) }}%</td>
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
  </section>
</template>
