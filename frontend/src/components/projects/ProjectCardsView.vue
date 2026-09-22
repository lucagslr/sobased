<script setup lang="ts">
/**
 * "Cartes" mode of the Projects page (SPEC §15, page 2): one big card per
 * root project, its sub-projects in three columns Passé / En cours / À venir,
 * the next deadline and the progress of the tasks.
 *
 * Everything is computed by the server (GET /api/projects/cards/), rights
 * included: a root I only see as a shell comes with nothing but its name, its
 * colour and the branches I can open. The budget joins in phase 7.
 */
import { CalendarClock, FolderTree } from 'lucide-vue-next'
import { ref, watch } from 'vue'
import { RouterLink } from 'vue-router'

import { type CardEntry, type ProjectCard, projectsApi, type Temporal } from '@/api/projects'
import ColorDot from '@/components/ui/ColorDot.vue'
import EmptyState from '@/components/ui/EmptyState.vue'
import SkeletonBlock from '@/components/ui/SkeletonBlock.vue'
import { useWorkspacesStore } from '@/stores/workspaces'
import { formatDate, formatDateRange, TEMPORAL_LABELS } from '@/utils/projects'

import StatusBadge from './StatusBadge.vue'

const emit = defineEmits<{ openTask: [id: number] }>()

const workspaces = useWorkspacesStore()
const cards = ref<ProjectCard[] | null>(null)
const COLUMNS: Temporal[] = ['past', 'current', 'upcoming']

async function load() {
  cards.value = null
  cards.value = await projectsApi.cards(
    workspaces.selection === 'all' ? undefined : workspaces.selection,
  )
}
watch(() => workspaces.selection, load, { immediate: true })
defineExpose({ reload: load })

function percent(stats: Pick<CardEntry, 'tasks_done' | 'tasks_total'>): number {
  return stats.tasks_total ? Math.round((stats.tasks_done / stats.tasks_total) * 100) : 0
}
</script>

<template>
  <div v-if="cards === null" class="space-y-4">
    <SkeletonBlock v-for="n in 2" :key="n" class="h-64 w-full" />
  </div>

  <EmptyState
    v-else-if="!cards.length"
    :icon="FolderTree"
    title="Aucun projet ici"
    text="Crée un projet racine (un artiste, une école, l'admin de l'asso) : il aura sa carte ici."
  />

  <div v-else class="space-y-5">
    <article
      v-for="card in cards"
      :key="card.id"
      class="rounded-2xl border border-line bg-surface p-4 sm:p-5"
    >
      <header class="flex flex-wrap items-start justify-between gap-x-6 gap-y-3">
        <div class="min-w-0">
          <h2 class="flex items-center gap-2.5 text-lg font-semibold tracking-tight">
            <ColorDot :color="card.color" size="md" />
            <RouterLink :to="`/projets/${card.id}`" class="truncate hover:underline">
              {{ card.name }}
            </RouterLink>
          </h2>
          <p class="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1.5 text-sm text-muted">
            <template v-if="card.is_shell">
              <span class="italic">Tu as accès à une partie de ce projet.</span>
            </template>
            <template v-else>
              <StatusBadge v-if="card.status" :status="card.status" :overdue="card.end_overdue" />
              <span>{{ card.type_name }}</span>
              <span v-if="card.start_date || card.end_date">
                {{ formatDateRange(card.start_date, card.end_date) }}
              </span>
            </template>
            <span v-if="workspaces.selection === 'all'">
              {{ workspaces.byId.get(card.workspace)?.name }}
            </span>
          </p>
        </div>

        <div class="w-full max-w-xs text-sm sm:w-64">
          <div class="flex items-center justify-between gap-3">
            <span class="text-muted">Avancement</span>
            <span class="font-medium">
              <template v-if="card.tasks_total">
                {{ card.tasks_done }}/{{ card.tasks_total }} · {{ percent(card) }} %
              </template>
              <template v-else>Aucune tâche</template>
            </span>
          </div>
          <div
            class="mt-1.5 h-1.5 overflow-hidden rounded-full bg-surface-2"
            role="progressbar"
            :aria-valuenow="percent(card)"
            aria-valuemin="0"
            aria-valuemax="100"
            :aria-label="`Avancement de ${card.name}`"
          >
            <div class="h-full rounded-full bg-accent" :style="{ width: `${percent(card)}%` }" />
          </div>
          <p v-if="card.tasks_overdue" class="mt-2 font-semibold text-danger">
            {{ card.tasks_overdue }} tâche{{ card.tasks_overdue > 1 ? 's' : '' }} en retard
          </p>
          <button
            v-if="card.next_due"
            type="button"
            class="mt-2 flex w-full items-start gap-2 text-left text-muted hover:text-fg"
            @click="emit('openTask', card.next_due.task)"
          >
            <CalendarClock class="mt-0.5 size-4 shrink-0" aria-hidden="true" />
            <span class="min-w-0">
              Prochaine échéance : <strong>{{ formatDate(card.next_due.date) }}</strong>
              <span class="block truncate">{{ card.next_due.title }}</span>
            </span>
          </button>
        </div>
      </header>

      <div class="mt-5 grid gap-3 md:grid-cols-3">
        <section
          v-for="key in COLUMNS"
          :key="key"
          class="rounded-xl bg-surface-2 p-2.5"
          :aria-label="`${TEMPORAL_LABELS[key]} · ${card.name}`"
        >
          <h3 class="flex items-center justify-between px-1.5 pt-0.5 pb-2 text-sm font-semibold">
            {{ TEMPORAL_LABELS[key] }}
            <span class="font-normal text-muted">{{ card[key].length }}</span>
          </h3>
          <ul class="space-y-2">
            <li v-for="entry in card[key]" :key="entry.id">
              <RouterLink
                :to="`/projets/${entry.id}`"
                class="block rounded-lg border border-line bg-surface p-3 hover:border-muted"
              >
                <span class="flex items-center gap-2 font-medium">
                  <ColorDot :color="entry.color" />
                  <span class="truncate">{{ entry.name }}</span>
                </span>
                <span class="mt-2 flex flex-wrap items-center gap-x-2 gap-y-1.5 text-xs text-muted">
                  <StatusBadge :status="entry.status" :overdue="entry.end_overdue" />
                  <span>{{ entry.type_name }}</span>
                </span>
                <span
                  v-if="entry.start_date || entry.end_date"
                  class="mt-1.5 block text-xs text-muted"
                >
                  {{ formatDateRange(entry.start_date, entry.end_date) }}
                </span>
                <span class="mt-2 flex items-center gap-2 text-xs text-muted">
                  <span
                    class="h-1 flex-1 overflow-hidden rounded-full bg-surface-2"
                    aria-hidden="true"
                  >
                    <span
                      class="block h-full rounded-full bg-accent"
                      :style="{ width: `${percent(entry)}%` }"
                    />
                  </span>
                  <span v-if="entry.tasks_total">
                    {{ entry.tasks_done }}/{{ entry.tasks_total }} tâches
                  </span>
                  <span v-else>Aucune tâche</span>
                </span>
                <span
                  v-if="entry.tasks_overdue || entry.children_count"
                  class="mt-1.5 flex flex-wrap gap-x-3 text-xs"
                >
                  <span v-if="entry.tasks_overdue" class="font-semibold text-danger">
                    {{ entry.tasks_overdue }} en retard
                  </span>
                  <span v-if="entry.children_count" class="text-muted">
                    {{ entry.children_count }} sous-projet{{ entry.children_count > 1 ? 's' : '' }}
                  </span>
                </span>
              </RouterLink>
            </li>
            <li v-if="!card[key].length" class="px-1.5 py-2 text-sm text-muted">—</li>
          </ul>
        </section>
      </div>
    </article>
  </div>
</template>
