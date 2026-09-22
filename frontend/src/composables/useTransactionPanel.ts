/**
 * The transaction panel is driven by the URL (?ecriture=42), like the task
 * and event panels; opening it closes the two others.
 */
import { computed } from 'vue'
import { type LocationQueryRaw, useRoute, useRouter } from 'vue-router'

export function useTransactionPanel() {
  const route = useRoute()
  const router = useRouter()

  const transactionId = computed(() => {
    const value = Number(route.query.ecriture)
    return Number.isInteger(value) && value > 0 ? value : null
  })

  function openTransaction(id: number) {
    const query: LocationQueryRaw = { ...route.query, ecriture: String(id) }
    delete query.tache
    delete query.rdv
    router.push({ query })
  }

  function closeTransaction() {
    const rest = { ...route.query }
    delete rest.ecriture
    router.replace({ query: rest })
  }

  return { transactionId, openTransaction, closeTransaction }
}
