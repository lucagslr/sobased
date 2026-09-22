<script setup lang="ts">
/**
 * External calendars (SPEC §12): which ones to display read-only in the
 * calendar view, which single one receives my SOBASED objects, reload the
 * lists, sync now, and the conflicts the sync had to settle.
 */
import { RefreshCw } from 'lucide-vue-next'
import { onMounted, ref } from 'vue'

import { ApiError } from '@/api/client'
import { type ExternalCalendar, integrationsApi, type SyncConflict } from '@/api/integrations'
import BaseButton from '@/components/ui/BaseButton.vue'
import ColorDot from '@/components/ui/ColorDot.vue'
import FormCard from '@/components/ui/FormCard.vue'
import { useUiStore } from '@/stores/ui'

const ui = useUiStore()
const calendars = ref<ExternalCalendar[] | null>(null)
const conflicts = ref<SyncConflict[]>([])
const busy = ref(false)

const PROVIDER_LABELS: Record<string, string> = { google: 'Google', microsoft: 'Outlook' }

async function load() {
  ;[calendars.value, conflicts.value] = await Promise.all([
    integrationsApi.calendars(),
    integrationsApi.syncConflicts(),
  ])
}
onMounted(load)

async function refresh() {
  busy.value = true
  try {
    calendars.value = await integrationsApi.refreshCalendars()
    ui.toast('Liste des calendriers rechargée', 'success')
  } catch (error) {
    ui.toast(error instanceof ApiError ? error.message : 'Rechargement impossible.', 'error')
  } finally {
    busy.value = false
  }
}

async function toggleDisplayed(calendar: ExternalCalendar, value: boolean) {
  try {
    const updated = await integrationsApi.updateCalendar(calendar.id, { is_displayed: value })
    calendars.value = (calendars.value ?? []).map((c) => (c.id === updated.id ? updated : c))
  } catch (error) {
    ui.toast(error instanceof ApiError ? error.message : 'Réglage non enregistré.', 'error')
  }
}

async function setTarget(calendar: ExternalCalendar) {
  try {
    await integrationsApi.updateCalendar(calendar.id, { is_target: true })
    calendars.value = await integrationsApi.calendars()
    ui.toast(`Mes tâches et RDV iront dans « ${calendar.name} »`, 'success')
  } catch (error) {
    ui.toast(error instanceof ApiError ? error.message : 'Réglage non enregistré.', 'error')
  }
}

async function syncNow() {
  busy.value = true
  try {
    await integrationsApi.syncNow()
    ui.toast(
      'Synchronisation lancée',
      'success',
      'Elle tourne en arrière-plan ; recharge dans une minute.',
    )
  } catch (error) {
    ui.toast(error instanceof ApiError ? error.message : 'Synchronisation impossible.', 'error')
  } finally {
    busy.value = false
  }
}

/** The two titles of a conflict, whatever shape `details` has. */
function conflictTitles(conflict: SyncConflict): { local: string; external: string } {
  const details = (conflict.details ?? {}) as Record<string, Record<string, string> | undefined>
  return { local: details.local?.title ?? '—', external: details.external?.title ?? '—' }
}

function when(iso: string | null): string {
  if (!iso) return 'jamais'
  return new Intl.DateTimeFormat('fr-CH', { dateStyle: 'short', timeStyle: 'short' }).format(
    new Date(iso),
  )
}
</script>

<template>
  <FormCard
    title="Calendriers"
    description="Choisis les calendriers à afficher en lecture dans SOBASED, et celui qui reçoit tes tâches (☐) et tes RDV. Synchronisation toutes les 5 minutes, dans les deux sens."
  >
    <p v-if="calendars === null" class="text-sm text-muted">Chargement…</p>
    <template v-else>
      <p v-if="!calendars.length" class="text-sm text-muted">
        Aucun calendrier chargé : connecte un compte avec l'accès calendrier, puis recharge la
        liste.
      </p>
      <ul v-else class="divide-y divide-line rounded-xl border border-line">
        <li
          v-for="calendar in calendars"
          :key="calendar.id"
          class="flex flex-wrap items-center gap-x-4 gap-y-2 px-3 py-2.5"
        >
          <span class="flex min-w-0 flex-1 items-center gap-2 text-sm">
            <ColorDot :color="calendar.color || '#e7e5e4'" />
            <span class="truncate font-medium">{{ calendar.name }}</span>
            <span class="shrink-0 text-xs text-muted">
              {{ PROVIDER_LABELS[calendar.provider] ?? calendar.provider }}
              <template v-if="calendar.is_primary"> · principal</template>
            </span>
          </span>
          <label class="flex items-center gap-1.5 text-xs">
            <input
              type="checkbox"
              class="size-4 accent-fg"
              :checked="calendar.is_displayed"
              @change="toggleDisplayed(calendar, ($event.target as HTMLInputElement).checked)"
            />
            Afficher
          </label>
          <label class="flex items-center gap-1.5 text-xs">
            <input
              type="radio"
              name="target-calendar"
              class="size-4 accent-fg"
              :checked="calendar.is_target"
              @change="setTarget(calendar)"
            />
            Reçoit mes tâches et RDV
          </label>
          <span
            v-if="calendar.is_displayed || calendar.is_target"
            class="w-full text-xs text-muted sm:w-auto"
          >
            synchro : {{ when(calendar.last_synced_at) }}
            <span v-if="calendar.last_error" class="text-danger"> · {{ calendar.last_error }}</span>
          </span>
        </li>
      </ul>
      <div class="mt-4 flex flex-wrap gap-2">
        <BaseButton variant="secondary" size="sm" :loading="busy" @click="refresh">
          <RefreshCw class="size-4" aria-hidden="true" /> Recharger la liste
        </BaseButton>
        <BaseButton
          v-if="calendars.some((c) => c.is_displayed || c.is_target)"
          variant="secondary"
          size="sm"
          :loading="busy"
          @click="syncNow"
        >
          Synchroniser maintenant
        </BaseButton>
      </div>
      <p class="mt-3 text-xs text-muted">
        Une suppression dans le calendrier externe ne supprime jamais rien dans SOBASED : l'objet
        cesse seulement d'être synchronisé. Les changements de titre remontent si tu es éditeur du
        projet ; un assigné peut déplacer la date de sa tâche.
      </p>
    </template>

    <div v-if="conflicts.length" class="mt-6">
      <h3 class="text-sm font-semibold">Conflits réglés</h3>
      <p class="mb-2 text-xs text-muted">
        Les deux côtés avaient changé : la modification la plus récente a gagné.
      </p>
      <ul class="divide-y divide-line text-sm">
        <li v-for="conflict in conflicts" :key="conflict.id" class="py-2">
          <p>
            <span class="font-medium">
              {{ conflict.object_type === 'task' ? 'Tâche' : 'RDV' }} ·
              {{
                conflict.winner === 'local'
                  ? 'SOBASED a gagné'
                  : `${conflict.calendar_name} a gagné`
              }}
            </span>
            <span class="text-xs text-muted"> · {{ when(conflict.created_at) }}</span>
          </p>
          <p class="text-xs text-muted">
            SOBASED : {{ conflictTitles(conflict).local }} · externe :
            {{ conflictTitles(conflict).external }}
          </p>
        </li>
      </ul>
    </div>
  </FormCard>
</template>
