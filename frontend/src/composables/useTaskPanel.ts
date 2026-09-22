/**
 * The task panel is driven by the URL (?tache=42), so a task can be linked
 * (e-mails point to it), survives a reload, and the Back button closes it.
 *
 * One panel at a time (SPEC §15: no stacked modals): opening a task closes
 * the event panel (?rdv=) in the same navigation, and vice versa.
 */
import { computed } from 'vue'
import { type LocationQueryRaw, useRoute, useRouter } from 'vue-router'

export function useTaskPanel() {
  const route = useRoute()
  const router = useRouter()

  const taskId = computed(() => {
    const value = Number(route.query.tache)
    return Number.isInteger(value) && value > 0 ? value : null
  })

  function openTask(id: number) {
    const query: LocationQueryRaw = { ...route.query, tache: String(id) }
    delete query.rdv
    router.push({ query })
  }

  function closeTask() {
    const rest = { ...route.query }
    delete rest.tache
    router.replace({ query: rest })
  }

  return { taskId, openTask, closeTask }
}
