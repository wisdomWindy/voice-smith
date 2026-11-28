<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { useEngineStore } from '../stores/engine'
import type { Job } from '../lib/engine'

const engine = useEngineStore()
const items = ref<Job[]>([])
const error = ref('')

async function load() {
  if (!engine.client) return
  try {
    items.value = await engine.client.jobs()
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  }
}

function saveBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  anchor.click()
  window.setTimeout(() => URL.revokeObjectURL(url), 1000)
}

async function download(item: Job, format: 'wav' | 'mp3') {
  if (!engine.client) return
  try {
    saveBlob(await engine.client.exportBlob(item.id, format), `${item.id}.${format}`)
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  }
}

watch(
  () => engine.status,
  (status) => {
    if (status === 'ready') void load()
  },
  { immediate: true },
)

onMounted(() => {
  if (engine.status === 'ready') void load()
})
</script>

<template>
  <section class="page">
    <div class="card">
      <div class="card-head">
        <div>
          <h2>合成记录</h2>
          <p class="muted small">本地任务与产物；音频只保存在本机。</p>
        </div>
        <button class="button ghost" @click="load">刷新</button>
      </div>
      <div v-if="error" class="inline-error">{{ error }}</div>
      <div class="table-wrap">
        <table class="table">
          <thead><tr><th>任务</th><th>文本</th><th>状态</th><th>进度</th><th>创建</th><th>导出</th></tr></thead>
          <tbody>
            <tr v-for="item in items" :key="item.id">
              <td class="muted small">{{ item.id }}</td>
              <td class="ellipsis" style="max-width:360px">{{ item.text }}</td>
              <td><span class="tag" :class="item.status">{{ item.status }}</span></td>
              <td>{{ item.progress }}%</td>
              <td class="muted small">{{ (item.created_at || '').slice(0, 19).replace('T', ' ') }}</td>
              <td>
                <div class="row gap">
                  <button class="button ghost small" :disabled="item.status !== 'succeeded'" @click="download(item, 'wav')">WAV</button>
                  <button class="button ghost small" :disabled="item.status !== 'succeeded'" @click="download(item, 'mp3')">MP3</button>
                </div>
              </td>
            </tr>
            <tr v-if="!items.length"><td colspan="6" class="muted">还没有任务。</td></tr>
          </tbody>
        </table>
      </div>
    </div>
  </section>
</template>
