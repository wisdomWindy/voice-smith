<script setup lang="ts">
import { ref, watch } from 'vue'
import { useEngineStore } from '../stores/engine'
import { isTauri, type Emotion, type Voice } from '../lib/engine'

const engine = useEngineStore()
const voices = ref<Voice[]>([])
const error = ref('')
const message = ref('')
const emotionVoiceId = ref('')
const emotionName = ref('平静')
const emotionPath = ref('')
const emotionText = ref('')
const emotions = ref<Emotion[]>([])
const emotionBusy = ref(false)

async function load() {
  if (!engine.client) return
  try {
    voices.value = await engine.client.voices()
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  }
}

async function loadEmotions() {
  if (!engine.client || !emotionVoiceId.value) {
    emotions.value = []
    return
  }
  try {
    emotions.value = await engine.client.emotions(emotionVoiceId.value)
  } catch {
    emotions.value = []
  }
}

async function browseEmotion() {
  if (!isTauri()) return
  const { invoke } = await import('@tauri-apps/api/core')
  const path = await invoke<string | null>('pick_audio_file')
  if (path) emotionPath.value = path
}

async function createEmotion() {
  if (!engine.client || !emotionVoiceId.value || !emotionPath.value.trim() || !emotionText.value.trim()) return
  emotionBusy.value = true
  error.value = ''
  try {
    await engine.client.createEmotion(
      emotionVoiceId.value,
      emotionName.value.trim() || '情绪',
      emotionPath.value.trim(),
      emotionText.value.trim(),
    )
    message.value = '情绪参考已添加，可在工作台选择。'
    await loadEmotions()
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  } finally {
    emotionBusy.value = false
  }
}

async function removeEmotion(item: Emotion) {
  if (!engine.client) return
  try {
    await engine.client.deleteEmotion(item.id)
    await loadEmotions()
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  }
}

watch(emotionVoiceId, () => {
  void loadEmotions()
})

watch(voices, (items) => {
  if (!emotionVoiceId.value && items.length) emotionVoiceId.value = items[0].id
})

async function remove(voice: Voice) {
  if (!engine.client) return
  if (!window.confirm(`删除音色「${voice.name}」？参考音频也会删除。`)) return
  try {
    await engine.client.deleteVoice(voice.id)
    await load()
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
</script>

<template>
  <section class="page">
    <div class="card">
      <div class="card-head">
        <div>
          <h2>音色库</h2>
          <p class="muted small">训练完成的音色会显示在这里；不再提供快速音色创建。</p>
        </div>
        <span class="tag">{{ voices.length }} 个</span>
      </div>
      <div v-if="error" class="inline-error">{{ error }}</div>
      <div v-if="message" class="banner" style="border-color:#1f4b3d;background:#0f1d19;color:#b8f5df">{{ message }}</div>

      <div class="voice-grid">
        <div v-for="voice in voices" :key="voice.id" class="voice-card">
          <div class="voice-avatar">{{ voice.name.slice(0, 1) }}</div>
          <div style="min-width:0">
            <strong>{{ voice.name }}</strong>
            <div class="muted small">{{ voice.type }} · {{ voice.status }}</div>
            <div class="muted tiny ellipsis">{{ voice.ref_text || voice.id }}</div>
          </div>
          <button v-if="voice.id !== 'demo_edge'" class="button ghost small" style="margin-left:auto" @click="remove(voice)">
            删除
          </button>
        </div>
      </div>
    </div>

    <div class="card">
      <div class="card-head">
        <div>
          <h2>情绪参考</h2>
          <p class="muted small">为音色绑定不同情绪的参考音频；推理时只切换参考音频，不改模型。</p>
        </div>
      </div>
      <div class="form-grid">
        <label class="field">
          <span>音色</span>
          <select v-model="emotionVoiceId" class="input">
            <option v-for="voice in voices" :key="voice.id" :value="voice.id">{{ voice.name }}</option>
          </select>
        </label>
        <label class="field">
          <span>情绪名</span>
          <input v-model="emotionName" class="input" placeholder="平静 / 紧张 / 开心" />
        </label>
        <label class="field" style="grid-column: span 2">
          <span>参考音频</span>
          <div class="row gap">
            <input v-model="emotionPath" class="input" style="flex:1" />
            <button v-if="isTauri()" class="button ghost" type="button" @click="browseEmotion">选择文件</button>
          </div>
        </label>
        <label class="field" style="grid-column: span 3">
          <span>参考音频转写</span>
          <input v-model="emotionText" class="input" />
        </label>
      </div>
      <button class="button primary" :disabled="emotionBusy || !emotionVoiceId || !emotionPath.trim() || !emotionText.trim()" @click="createEmotion">
        {{ emotionBusy ? '保存中…' : '添加情绪参考' }}
      </button>
      <div class="voice-grid" style="margin-top:12px">
        <div v-for="item in emotions" :key="item.id" class="voice-card">
          <div>
            <strong>{{ item.name }}</strong>
            <div class="muted tiny ellipsis">{{ item.ref_text }}</div>
          </div>
          <button class="button ghost small" style="margin-left:auto" @click="removeEmotion(item)">删除</button>
        </div>
      </div>
    </div>
  </section>
</template>
