<script setup lang="ts">
import { computed, ref } from 'vue'
import { isTauri } from '../lib/engine'
import { addDataset, datasets, deleteDataset } from '../lib/datasets'
import { selectedProject } from '../lib/projects'

const name = ref('')
const rawAudio = ref('')
const error = ref('')
const visibleDatasets = computed(() => datasets.value.filter((item) => item.projectId === selectedProject.value?.id))

async function browse() {
  if (!isTauri()) return
  const { invoke } = await import('@tauri-apps/api/core')
  const path = await invoke<string | null>('pick_audio_file')
  if (path) {
    rawAudio.value = path
    if (!name.value) name.value = path.split(/[\\/]/).pop()?.replace(/\.[^.]+$/, '') || '数据集'
  }
}

function create() {
  if (!selectedProject.value) {
    error.value = '请先在「项目」页面选择项目'
    return
  }
  if (!rawAudio.value.trim()) {
    error.value = '请选择原始音频'
    return
  }
  error.value = ''
  addDataset(name.value, rawAudio.value.trim(), selectedProject.value.id)
  name.value = ''
  rawAudio.value = ''
}

function remove(id: string) {
  if (window.confirm('删除这个数据集？原始音频文件不会被删除。')) deleteDataset(id)
}
</script>

<template>
  <section class="page">
    <div class="card">
      <div class="card-head">
        <div>
          <h2>数据集</h2>
          <p class="muted small">上传原始音频，创建一个待预处理的数据集。</p>
        </div>
        <span class="tag">{{ visibleDatasets.length }} 个</span>
      </div>
      <div v-if="error" class="inline-error">{{ error }}</div>
      <label class="field">
        <span>原始音频</span>
        <div class="row gap">
          <input v-model="rawAudio" class="input" style="flex:1" placeholder="选择歌曲、录音或含人声的音频" />
          <button v-if="isTauri()" class="button ghost" @click="browse">选择文件</button>
        </div>
      </label>
      <label class="field">
        <span>数据集名称</span>
        <input v-model="name" class="input" placeholder="例如 我的声音" />
      </label>
      <button class="button primary" :disabled="!rawAudio.trim()" @click="create">创建数据集</button>
    </div>

    <div class="card" style="margin-top:16px">
      <div class="card-head"><h2>数据集列表</h2></div>
      <table class="table">
        <thead><tr><th>名称</th><th>状态</th><th>原始音频</th><th>操作</th></tr></thead>
        <tbody>
          <tr v-for="item in visibleDatasets" :key="item.id">
            <td>{{ item.name }}</td>
            <td>{{ item.status === 'raw' ? '待预处理' : '已预处理' }}</td>
            <td class="ellipsis">{{ item.rawAudio }}</td>
            <td><button class="button ghost small" @click="remove(item.id)">删除</button></td>
          </tr>
          <tr v-if="!visibleDatasets.length"><td colspan="4" class="muted">还没有数据集。</td></tr>
        </tbody>
      </table>
    </div>
  </section>
</template>
