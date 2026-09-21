/**
 * The task panel is driven by the URL (?tache=42), so a task can be linked
 * (e-mails point to it), survives a reload, and the Back button closes it.
 */
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'

export function useTaskPanel() {
  const route = useRoute()
  const router = useRouter()

  const taskId = computed(() => {
    const value = Number(route.query.tache)
    return Number.isInteger(value) && value > 0 ? value : null
  })

  function openTask(id: number) {
    router.push({ query: { ...route.query, tache: String(id) } })
  }

  function closeTask() {
    const rest = { ...route.query }
    delete rest.tache
    router.replace({ query: rest })
  }

  return { taskId, openTask, closeTask }
}
