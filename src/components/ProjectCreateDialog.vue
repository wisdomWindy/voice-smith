<script setup lang="ts">
import { nextTick, ref, watch } from 'vue'

const props = defineProps<{
  open: boolean
  busy?: boolean
  error?: string
}>()

const emit = defineEmits<{ create: [name: string]; cancel: [] }>()

const name = ref('')
const input = ref<HTMLInputElement | null>(null)

watch(
  () => props.open,
  async (open) => {
    document.body.style.overflow = open ? 'hidden' : ''
    if (open) {
      name.value = ''
      await nextTick()
      input.value?.focus()
    }
  },
)

function submit() {
  const value = name.value.trim()
  if (!value || props.busy) return
  emit('create', value)
}
</script>

<template>
  <Teleport to="body">
    <Transition name="project-dialog">
      <div v-if="open" class="project-mask" @click.self="emit('cancel')">
        <div class="project-dialog" role="dialog" aria-modal="true" aria-label="创建项目">
          <div class="project-head">
            <div class="project-icon">VS</div>
            <div>
              <h3>创建项目</h3>
              <p>项目会创建在安装目录的 <code>projects</code> 文件夹中。</p>
            </div>
          </div>
          <label class="project-field">
            <span>项目名称</span>
            <input
              ref="input"
              v-model="name"
              maxlength="60"
              placeholder="例如：短视频配音"
              @keydown.enter.prevent="submit"
              @keydown.esc.prevent="emit('cancel')"
            />
          </label>
          <p v-if="error" class="project-error">{{ error }}</p>
          <p class="project-hint">名称会直接作为文件夹名，不能包含 <code>\ / : * ? " &lt; &gt; |</code>。</p>
          <div class="project-actions">
            <button type="button" class="project-button ghost" :disabled="busy" @click="emit('cancel')">
              取消
            </button>
            <button
              type="button"
              class="project-button primary"
              :disabled="busy || !name.trim()"
              @click="submit"
            >
              {{ busy ? '创建中…' : '创建' }}
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.project-mask {
  position: fixed;
  inset: 0;
  z-index: 200;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  background: rgba(4, 7, 12, 0.72);
  backdrop-filter: blur(3px);
}
.project-dialog {
  width: min(460px, 100%);
  display: grid;
  gap: 15px;
  padding: 22px;
  border: 1px solid #263349;
  border-radius: 16px;
  background: linear-gradient(180deg, #151c27, #10151e);
  box-shadow: 0 24px 80px rgba(0, 0, 0, 0.55);
}
.project-head {
  display: flex;
  gap: 12px;
  align-items: flex-start;
}
.project-icon {
  width: 38px;
  height: 38px;
  display: grid;
  place-items: center;
  flex: none;
  border-radius: 11px;
  color: #dfe8ff;
  font-size: 12px;
  font-weight: 700;
  background: linear-gradient(135deg, #6f8fff, #4d6fe0);
}
.project-head h3 {
  margin: 1px 0 5px;
  font-size: 16px;
  color: #eef3fb;
}
.project-head p,
.project-hint {
  margin: 0;
  color: #8d9bb0;
  font-size: 12px;
  line-height: 1.6;
}
.project-head code,
.project-hint code {
  color: #aebfe0;
  font-size: 11px;
}
.project-field {
  display: grid;
  gap: 7px;
  font-size: 12px;
  color: #9aa8bd;
}
.project-field input {
  height: 38px;
  padding: 0 12px;
  border-radius: 9px;
  border: 1px solid #2b3a52;
  background: #0d121a;
  color: #eef3fb;
  outline: none;
}
.project-field input:focus {
  border-color: #6f8fff;
  box-shadow: 0 0 0 3px rgba(111, 143, 255, 0.13);
}
.project-error {
  margin: 0;
  padding: 8px 10px;
  border-radius: 8px;
  border: 1px solid #4b2323;
  background: #1a1111;
  color: #ffb3b3;
  font-size: 12px;
}
.project-actions {
  display: flex;
  justify-content: flex-end;
  gap: 9px;
  margin-top: 2px;
}
.project-button {
  min-height: 35px;
  padding: 0 16px;
  border-radius: 9px;
  border: 1px solid transparent;
  font-size: 13px;
  color: #eaf0fa;
}
.project-button.ghost {
  background: transparent;
  border-color: #2b3a52;
  color: #aebbd0;
}
.project-button.ghost:hover {
  background: #1a2230;
}
.project-button.primary {
  background: linear-gradient(180deg, #6f8fff, #5b7df0);
  border-color: #5b7df0;
  font-weight: 600;
}
.project-button:disabled {
  opacity: 0.45;
  cursor: default;
}
.project-dialog-enter-active,
.project-dialog-leave-active {
  transition: opacity 0.16s ease;
}
.project-dialog-enter-active .project-dialog,
.project-dialog-leave-active .project-dialog {
  transition: transform 0.16s ease, opacity 0.16s ease;
}
.project-dialog-enter-from,
.project-dialog-leave-to {
  opacity: 0;
}
.project-dialog-enter-from .project-dialog,
.project-dialog-leave-to .project-dialog {
  transform: translateY(6px) scale(0.98);
  opacity: 0;
}
</style>
