import { ref } from 'vue'
import { useProjectStore, type EntityRow, type RolloutStatus } from '../stores/project.ts'

/** 台账行「调态」抽屉的编辑状态与保存动作。 */
export function useEntityEditor() {
  const store = useProjectStore()
  const editing = ref<EntityRow | null>(null)
  const draft = ref<Partial<EntityRow>>({})

  function open(row: EntityRow) {
    editing.value = row
    draft.value = { ...row }
  }

  function close() {
    editing.value = null
  }

  function save() {
    if (!editing.value) return
    store.updateEntity(editing.value.id, {
      status: draft.value.status as RolloutStatus,
      construction: Number(draft.value.construction),
      openingData: Number(draft.value.openingData),
      owner: String(draft.value.owner),
    })
    editing.value = null
  }

  return { editing, draft, open, close, save }
}
