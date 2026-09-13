import { ref } from 'vue'
import { useProjectStore, type EntityRow, type RolloutStatus } from '../stores/project.ts'

const API_BASE = import.meta.env.VITE_API_BASE_URL || ''

/** 台账行「调态」对话框的编辑状态与保存动作。 */
export function useEntityEditor() {
  const store = useProjectStore()
  const editing = ref<EntityRow | null>(null)
  const draft = ref<Partial<EntityRow>>({})
  const saving = ref(false)
  const error = ref<string | null>(null)

  function open(row: EntityRow) {
    editing.value = row
    draft.value = { ...row }
    error.value = null
  }

  function close() {
    editing.value = null
    error.value = null
  }

  async function save() {
    if (!editing.value) return
    
    saving.value = true
    error.value = null
    
    const patch: Record<string, unknown> = {}
    
    if (draft.value.status !== editing.value.status) {
      patch.status = draft.value.status
    }
    if (draft.value.owner !== editing.value.owner) {
      patch.owner = draft.value.owner
    }
    if (draft.value.construction !== editing.value.construction) {
      patch.construction = Number(draft.value.construction)
    }
    if (draft.value.openingData !== editing.value.openingData) {
      patch.opening_data = Number(draft.value.openingData)
    }
    
    // 如果没有任何变更，直接关闭
    if (Object.keys(patch).length === 0) {
      editing.value = null
      saving.value = false
      return
    }
    
    try {
      const resp = await fetch(`${API_BASE}/api/organizations/${editing.value.id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(patch),
      })
      
      if (!resp.ok) {
        const data = await resp.json().catch(() => ({}))
        throw new Error(data.detail || `HTTP ${resp.status}`)
      }
      
      // 更新本地状态（乐观更新）
      store.updateEntity(editing.value.id, {
        status: draft.value.status as RolloutStatus,
        construction: Number(draft.value.construction),
        openingData: Number(draft.value.openingData),
        owner: String(draft.value.owner),
      })
      
      editing.value = null
    } catch (e) {
      error.value = e instanceof Error ? e.message : '保存失败'
      console.error('[useEntityEditor] save failed:', e)
    } finally {
      saving.value = false
    }
  }

  return { editing, draft, saving, error, open, close, save }
}
