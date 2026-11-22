<script setup lang="ts">
import { ref } from 'vue'
import { isTauri } from '../lib/engine'
import {
  addProject,
  projects,
  removeProject,
  selectProject,
  selectedProjectId,
} from '../lib/projects'

const error = ref('')
const busy = ref(false)

async function createProject() {
  if (!isTauri()) {
    error.value = '仅桌面端支持创建项目'
    return
  }
  busy.value = true
  error.value = ''
  try {
    const { invoke } = await import('@tauri-apps/api/core')
    const path = await invoke<string>('create_project')
    addProject(path)
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  } finally {
    busy.value = false
  }
}

async function openFolder(path: string) {
  if (!isTauri()) return
  const { openPath } = await import('@tauri-apps/plugin-opener')
  await openPath(path)
}

function remove(id: string, name: string) {
  if (!window.confirm(`删除项目「${name}」？\n只从项目列表移除，不删除磁盘文件夹。`)) return
  removeProject(id)
}
</script>

<template>
  <section class="page">
    <div class="card">
      <div class="card-head">
        <div>
          <h2>项目</h2>
          <p class="muted small">每个项目使用一个独立文件夹保存数据集、训练和推理产物。</p>
          <p class="muted small">项目固定创建在安装目录的 <code>projects</code> 文件夹中，不能更改位置。</p>
        </div>
        <button class="button primary" :disabled="busy" @click="createProject">
          {{ busy ? '创建中…' : '创建项目' }}
        </button>
      </div>
      <div v-if="error" class="inline-error">{{ error }}</div>
      <p class="muted small">点击项目卡片选中项目，后续数据集、预处理、训练和推理都在选中项目中进行。</p>
    </div>

    <div class="voice-grid" style="margin-top:16px">
      <div
        v-for="project in projects"
        :key="project.id"
        class="voice-card"
        :style="project.id === selectedProjectId ? 'border-color:#7c5cff;box-shadow:0 0 0 1px #7c5cff' : ''"
        @click="selectProject(project.id)"
      >
        <div class="voice-avatar">{{ project.name.slice(0, 1) }}</div>
        <div style="min-width:0;flex:1">
          <strong>{{ project.name }}</strong>
          <div class="muted tiny ellipsis">{{ project.path }}</div>
          <div class="muted tiny">{{ project.id === selectedProjectId ? '已选中' : '未选中' }}</div>
        </div>
        <div class="row gap">
          <button class="button ghost small" @click.stop="openFolder(project.path)">打开项目</button>
          <button class="button ghost small" @click.stop="remove(project.id, project.name)">删除</button>
        </div>
      </div>
    </div>
    <p v-if="!projects.length" class="muted small">还没有项目，点击右上角「创建项目」。</p>
  </section>
</template>
