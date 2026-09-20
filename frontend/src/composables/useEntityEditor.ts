import { ref } from 'vue'
import { requestJson } from '../api/http.ts'
import { useProjectStore, type EntityRow, type RolloutStatus } from '../stores/project.ts'

interface EntityEditorOptions {
  onSaved?: (id: number, patch: Partial<EntityRow>) => void
}

/** 台账行「调态」对话框的编辑状态与保存动作。 */
export function useEntityEditor(options: EntityEditorOptions = {}) {
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
      const id = editing.value.id
      await requestJson<{ ok: true; id: number }>(`organizations/${id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(patch),
      })

      const localPatch: Partial<EntityRow> = {
        status: draft.value.status as RolloutStatus,
        construction: Number(draft.value.construction),
        openingData: Number(draft.value.openingData),
        owner: String(draft.value.owner),
      }
      store.updateEntity(id, localPatch)
      options.onSaved?.(id, localPatch)
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
