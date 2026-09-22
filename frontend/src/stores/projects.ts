/**
 * The project tree. The API returns every visible node as a flat list
 * (shells included); nesting and filtering by workspace happen here.
 */
import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

import { type ProjectNode, projectsApi, type TasksView } from '@/api/projects'
import { buildTree, type TreeNode } from '@/utils/projects'

import { useWorkspacesStore } from './workspaces'

export const useProjectsStore = defineStore('projects', () => {
  const nodes = ref<ProjectNode[]>([])
  const loaded = ref(false)
  const showArchived = ref(false)
  /** Task view chosen on a project during this visit (the server has it too;
   * this only covers the time until the project is fetched again). */
  const tasksViews = new Map<number, TasksView>()

  const byId = computed(() => new Map(nodes.value.map((node) => [node.id, node])))

  /** Roots of the workspace selected in the sidebar (or of all of them). */
  const tree = computed<TreeNode[]>(() => {
    const selection = useWorkspacesStore().selection
    const visible =
      selection === 'all' ? nodes.value : nodes.value.filter((n) => n.workspace === selection)
    return buildTree(visible)
  })

  async function load() {
    nodes.value = await projectsApi.tree(showArchived.value)
    loaded.value = true
  }

  function childrenOf(projectId: number): ProjectNode[] {
    return nodes.value
      .filter((node) => node.parent === projectId)
      .sort((a, b) => a.position - b.position || a.name.localeCompare(b.name, 'fr'))
  }

  function reset() {
    nodes.value = []
    loaded.value = false
    tasksViews.clear()
  }

  return { nodes, loaded, showArchived, tasksViews, byId, tree, load, childrenOf, reset }
})
