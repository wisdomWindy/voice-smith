<script setup lang="ts">
import { ref, watch } from 'vue'
import { useEngineStore } from '../stores/engine'
import type { ModelFile } from '../lib/engine'

const engine = useEngineStore()
const items = ref<ModelFile[]>([])
const error = ref('')
const message = ref('')

async function load() {
  if (!engine.client) return
  try {
    items.value = await engine.client.models()
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  }
}

async function remove(item: ModelFile) {
  if (!engine.client) return
  if (!window.confirm(`删除模型文件「${item.name}」？该文件不可恢复。`)) return
  try {
    await engine.client.deleteModel(item.id)
    message.value = `已删除 ${item.name}`
    await load()
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  }
}

function size(bytes: number) {
  if (bytes >= 1024 ** 3) return `${(bytes / 1024 ** 3).toFixed(2)} GB`
  if (bytes >= 1024 ** 2) return `${(bytes / 1024 ** 2).toFixed(1)} MB`
  return `${Math.round(bytes / 1024)} KB`
}

watch(
  () => engine.status,
  (status) => {
    if (status === 'ready') void load()
  },
  { immediate: true },
)
</script>

<template>
  <section class="page">
    <div class="card">
      <div class="card-head">
        <div>
          <h2>训练产出模型</h2>
          <p class="muted small">训练产出的 S1/S2 权重；删除前确认没有被音色引用。</p>
        </div>
        <button class="button ghost" @click="load">刷新</button>
      </div>
      <div v-if="error" class="inline-error">{{ error }}</div>
      <div v-if="message" class="banner success">{{ message }}</div>
      <div class="table-wrap">
        <table class="table">
          <thead><tr><th>实验</th><th>类型</th><th>文件</th><th>大小</th><th>修改时间</th><th></th></tr></thead>
          <tbody>
            <tr v-for="item in items" :key="item.id">
              <td>{{ item.experiment }}</td>
              <td><span class="tag">{{ item.kind }}</span></td>
              <td class="mono small">{{ item.name }}</td>
              <td>{{ size(item.size) }}</td>
              <td class="muted small">{{ item.modified_at.slice(0, 19).replace('T', ' ') }}</td>
              <td><button class="button danger small" @click="remove(item)">删除</button></td>
            </tr>
            <tr v-if="!items.length"><td colspan="6" class="muted">还没有训练模型。</td></tr>
          </tbody>
        </table>
      </div>
    </div>
  </section>
</template>
