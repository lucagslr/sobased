/**
 * Workspaces the user can see, the one currently selected in the sidebar
 * ("all" is a valid choice), and the per-workspace lists (types, tags).
 */
import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

import { type ProjectType, type Tag, type Workspace, workspacesApi } from '@/api/projects'

const STORAGE_KEY = 'faiblegraine-workspace'
export type WorkspaceSelection = 'all' | number

function storedSelection(): WorkspaceSelection {
  try {
    const value = localStorage.getItem(STORAGE_KEY)
    return value && value !== 'all' ? Number(value) : 'all'
  } catch {
    return 'all'
  }
}

export const useWorkspacesStore = defineStore('workspaces', () => {
  const items = ref<Workspace[]>([])
  const loaded = ref(false)
  const selection = ref<WorkspaceSelection>(storedSelection())
  const typesByWorkspace = ref<Record<number, ProjectType[]>>({})
  const tagsByWorkspace = ref<Record<number, Tag[]>>({})

  const byId = computed(() => new Map(items.value.map((w) => [w.id, w])))
  /** Workspaces where I am a real member (not just a guest of a sub-project). */
  const joined = computed(() => items.value.filter((w) => !w.is_shell))
  const current = computed(() =>
    selection.value === 'all' ? null : (byId.value.get(selection.value) ?? null),
  )

  async function load() {
    items.value = await workspacesApi.list()
    loaded.value = true
    // The remembered workspace may have been deleted or left since.
    if (selection.value !== 'all' && !byId.value.has(selection.value)) select('all')
  }

  function select(choice: WorkspaceSelection) {
    selection.value = choice
    try {
      localStorage.setItem(STORAGE_KEY, String(choice))
    } catch {
      /* not persisted in private browsing */
    }
  }

  async function create(name: string, color: string) {
    const workspace = await workspacesApi.create({ name, color })
    await load()
    return workspace
  }

  async function loadTypes(workspaceId: number, force = false) {
    if (force || !typesByWorkspace.value[workspaceId]) {
      typesByWorkspace.value[workspaceId] = await workspacesApi.projectTypes(workspaceId)
    }
    return typesByWorkspace.value[workspaceId]
  }

  async function loadTags(workspaceId: number, force = false) {
    if (force || !tagsByWorkspace.value[workspaceId]) {
      tagsByWorkspace.value[workspaceId] = await workspacesApi.tags(workspaceId)
    }
    return tagsByWorkspace.value[workspaceId]
  }

  function reset() {
    items.value = []
    loaded.value = false
    typesByWorkspace.value = {}
    tagsByWorkspace.value = {}
  }

  return {
    items,
    loaded,
    selection,
    byId,
    joined,
    current,
    typesByWorkspace,
    tagsByWorkspace,
    load,
    select,
    create,
    loadTypes,
    loadTags,
    reset,
  }
})
