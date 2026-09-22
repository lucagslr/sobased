/**
 * The event panel is driven by the URL (?rdv=42), like the task panel: an
 * event can be linked, survives a reload, and the Back button closes it.
 * Opening an event closes the task panel (?tache=) in the same navigation.
 */
import { computed } from 'vue'
import { type LocationQueryRaw, useRoute, useRouter } from 'vue-router'

export function useEventPanel() {
  const route = useRoute()
  const router = useRouter()

  const eventId = computed(() => {
    const value = Number(route.query.rdv)
    return Number.isInteger(value) && value > 0 ? value : null
  })

  function openEvent(id: number) {
    const query: LocationQueryRaw = { ...route.query, rdv: String(id) }
    delete query.tache
    router.push({ query })
  }

  function closeEvent() {
    const rest = { ...route.query }
    delete rest.rdv
    router.replace({ query: rest })
  }

  return { eventId, openEvent, closeEvent }
}
