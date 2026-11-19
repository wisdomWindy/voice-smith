import { defineStore } from 'pinia'
import {
  EngineClient,
  getEngineInfo,
  installRuntime,
  isTauri,
  restartEngine,
  runtimeStatus,
  type EngineInfo,
  type Health,
  type RuntimeStatus,
} from '../lib/engine'

export const useEngineStore = defineStore('engine', {
  state: () => ({
    info: null as EngineInfo | null,
    client: null as EngineClient | null,
    status: 'starting' as 'starting' | 'ready' | 'error' | 'runtime_missing',
    error: '',
    health: null as Health | null,
  }),
  getters: {
    ready: (state) => state.status === 'ready' && Boolean(state.client),
  },
  actions: {
    async init() {
      this.status = 'starting'
      this.error = ''
      try {
        const info = await getEngineInfo()
        this.info = info
        if (info.status === 'runtime_missing') {
          this.status = 'runtime_missing'
          return
        }
        this.client = new EngineClient(info.port, info.token)
        this.health = await this.client.waitUntilReady()
        this.status = 'ready'
      } catch (error) {
        this.status = 'error'
        this.error = error instanceof Error ? error.message : String(error)
      }
    },
    async runtime(): Promise<RuntimeStatus> {
      return runtimeStatus()
    },
    async installRuntimePack(url: string, sha256 = ''): Promise<boolean> {
      this.status = 'starting'
      this.error = ''
      try {
        const info = await installRuntime(url, sha256)
        this.info = info
        if (info.status === 'runtime_missing') {
          this.status = 'runtime_missing'
          return false
        }
        this.client = new EngineClient(info.port, info.token)
        this.health = await this.client.waitUntilReady()
        this.status = 'ready'
        return true
      } catch (error) {
        this.status = 'error'
        this.error = error instanceof Error ? error.message : String(error)
        return false
      }
    },
    async restart() {
      this.status = 'starting'
      this.error = ''
      try {
        const info = isTauri() ? await restartEngine() : await getEngineInfo()
        this.info = info
        if (info.status === 'runtime_missing') {
          this.status = 'runtime_missing'
          return
        }
        this.client = new EngineClient(info.port, info.token)
        this.health = await this.client.waitUntilReady()
        this.status = 'ready'
      } catch (error) {
        this.status = 'error'
        this.error = error instanceof Error ? error.message : String(error)
      }
    },
  },
})
