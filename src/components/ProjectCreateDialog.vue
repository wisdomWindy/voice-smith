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
  gap: 14px;
  padding: 20px;
  border: 1px solid var(--line);
  border-radius: 12px;
  background: var(--panel);
  box-shadow: 0 24px 80px rgba(0, 0, 0, 0.55);
}
.project-head {
  display: flex;
  gap: 12px;
  align-items: flex-start;
}
.project-icon {
  width: 36px;
  height: 36px;
  display: grid;
  place-items: center;
  flex: none;
  border-radius: 10px;
  color: #fff;
  font-size: 11px;
  font-weight: 700;
  background: var(--accent);
}
.project-head h3 {
  margin: 1px 0 5px;
  font-size: 15px;
  color: var(--text);
}
.project-head p,
.project-hint {
  margin: 0;
  color: var(--muted);
  font-size: 12px;
  line-height: 1.6;
}
.project-head code,
.project-hint code {
  color: var(--text);
  font-size: 11px;
}
.project-field {
  display: grid;
  gap: 7px;
  font-size: 12px;
  color: var(--muted);
}
.project-field input {
  height: 34px;
  padding: 0 10px;
  border-radius: 8px;
  border: 1px solid var(--line);
  background: var(--bg);
  color: var(--text);
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
  border: 1px solid rgba(223, 91, 91, 0.4);
  background: rgba(223, 91, 91, 0.08);
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
  min-height: 32px;
  padding: 0 14px;
  border-radius: 8px;
  border: 1px solid transparent;
  font-size: 13px;
  font-weight: 500;
  color: var(--text);
}
.project-button.ghost {
  background: transparent;
  border-color: var(--line);
  color: var(--muted);
}
.project-button.ghost:hover {
  background: var(--panel-2);
  color: var(--text);
}
.project-button.primary {
  background: var(--accent);
  border-color: var(--accent);
  font-weight: 600;
}
.project-button.primary:hover {
  background: var(--accent-2);
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
}</style>
