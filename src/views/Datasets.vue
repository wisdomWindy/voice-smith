<script setup lang="ts">
import { computed, ref } from 'vue'
import { isTauri } from '../lib/engine'
import { addDataset, datasets, deleteDataset } from '../lib/datasets'
import { selectedProject } from '../lib/projects'

const name = ref('')
const rawAudios = ref<string[]>([])
const error = ref('')
const message = ref('')
const visibleDatasets = computed(() => datasets.value.filter((item) => item.projectId === selectedProject.value?.id))

function stem(path: string): string {
  return path.split(/[\\/]/).pop()?.replace(/\.[^.]+$/, '') || '数据集'
}

async function browse() {
  if (!isTauri()) return
  const { invoke } = await import('@tauri-apps/api/core')
  const paths = await invoke<string[]>('pick_audio_files')
  if (!paths.length) return
  const merged = [...rawAudios.value]
  for (const path of paths) {
    if (!merged.some((item) => item.toLowerCase() === path.toLowerCase())) merged.push(path)
  }
  rawAudios.value = merged
  if (!name.value && merged.length === 1) name.value = stem(merged[0])
}

function removePending(path: string) {
  rawAudios.value = rawAudios.value.filter((item) => item !== path)
}

function create() {
  if (!selectedProject.value) {
    error.value = '请先在「项目」页面选择项目'
    return
  }
  if (!rawAudios.value.length) {
    error.value = '请选择原始音频'
    return
  }
  error.value = ''
  const label = name.value.trim() || stem(rawAudios.value[0])
  addDataset(label, rawAudios.value, selectedProject.value.id)
  message.value = `已创建 1 个数据集，包含 ${rawAudios.value.length} 个音频`
  name.value = ''
  rawAudios.value = []
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
          <p class="muted small">上传原始音频，创建一个待预处理的数据集；一次可选中多个音频，它们属于同一个数据集。</p>
        </div>
        <span class="tag">{{ visibleDatasets.length }} 个</span>
      </div>
      <div v-if="error" class="inline-error">{{ error }}</div>
      <div v-if="message" class="banner" style="border-color:#1f4b3d;background:#0f1d19;color:#b8f5df">{{ message }}</div>
      <label class="field">
        <span>原始音频</span>
        <div class="row gap">
          <input
            class="input"
            style="flex:1"
            :value="rawAudios.length ? `已选择 ${rawAudios.length} 个文件` : ''"
            readonly
            placeholder="选择歌曲、录音或含人声的音频，可多选"
          />
          <button v-if="isTauri()" class="button ghost" @click="browse">选择音频</button>
        </div>
      </label>
      <ul v-if="rawAudios.length" class="pending-files">
        <li v-for="path in rawAudios" :key="path">
          <span class="ellipsis">{{ path }}</span>
          <button class="button ghost small" @click="removePending(path)">移除</button>
        </li>
      </ul>
      <label class="field">
        <span>数据集名称（可选）</span>
        <input v-model="name" class="input" placeholder="留空则使用第一个音频的文件名" />
      </label>
      <button class="button primary" :disabled="!rawAudios.length" @click="create">
        创建数据集
      </button>
    </div>

    <div class="card" style="margin-top:16px">
      <div class="card-head"><h2>数据集列表</h2></div>
      <table class="table">
        <thead><tr><th>名称</th><th>状态</th><th>原始音频</th><th>操作</th></tr></thead>
        <tbody>
          <tr v-for="item in visibleDatasets" :key="item.id">
            <td>{{ item.name }}</td>
            <td>{{ item.status === 'raw' ? '待预处理' : '已预处理' }}</td>
            <td class="ellipsis">{{ item.rawAudios.length }} 个音频 · {{ item.rawAudios[0] }}</td>
            <td><button class="button ghost small" @click="remove(item.id)">删除</button></td>
          </tr>
          <tr v-if="!visibleDatasets.length"><td colspan="4" class="muted">还没有数据集。</td></tr>
        </tbody>
      </table>
    </div>
  </section>
</template>

<style scoped>
.pending-files {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  gap: 6px;
}
.pending-files li {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 7px 10px;
  border: 1px solid #263349;
  border-radius: 8px;
  background: #0e141d;
  font-size: 12px;
}
.pending-files li span {
  flex: 1;
  min-width: 0;
  color: #aebbd0;
}
</style>
