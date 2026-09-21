<script setup lang="ts">
/**
 * Overview of a project. Today: description + sub-projects sorted into
 * Passé / En cours / À venir. The mini-dashboard (overdue, today, milestones,
 * budget) is added in phase 4.
 */
import { computed } from 'vue'
import { RouterLink } from 'vue-router'

import type { Project, Temporal } from '@/api/projects'
import StatusBadge from '@/components/projects/StatusBadge.vue'
import ColorDot from '@/components/ui/ColorDot.vue'
import { useProjectsStore } from '@/stores/projects'
import { formatDateRange, TEMPORAL_LABELS } from '@/utils/projects'

const props = defineProps<{ project: Project }>()
const projects = useProjectsStore()

const COLUMNS: Temporal[] = ['past', 'current', 'upcoming']
const children = computed(() => projects.childrenOf(props.project.id))
const byTemporal = computed(() =>
  Object.fromEntries(
    COLUMNS.map((key) => [key, children.value.filter((child) => child.temporal === key)]),
  ),
)
</script>

<template>
  <div class="space-y-8">
    <section v-if="project.description">
      <h2 class="mb-2 text-sm font-semibold text-muted">Description</h2>
      <p class="max-w-3xl whitespace-pre-line">{{ project.description }}</p>
    </section>

    <section>
      <h2 class="mb-3 text-sm font-semibold text-muted">Sous-projets</h2>
      <p v-if="!children.length" class="text-sm text-muted">Aucun sous-projet pour l'instant.</p>
      <div v-else class="grid gap-4 md:grid-cols-3">
        <div v-for="key in COLUMNS" :key="key" class="rounded-2xl border border-line p-3">
          <h3 class="mb-2 px-1 text-sm font-semibold">
            {{ TEMPORAL_LABELS[key] }}
            <span class="font-normal text-muted">{{ byTemporal[key].length }}</span>
          </h3>
          <ul class="space-y-2">
            <li v-for="child in byTemporal[key]" :key="child.id">
              <RouterLink
                :to="`/projets/${child.id}`"
                class="block rounded-xl border border-line bg-surface p-3 hover:bg-surface-2"
              >
                <span class="flex items-center gap-2 font-medium">
                  <ColorDot :color="child.color" /> <span class="truncate">{{ child.name }}</span>
                </span>
                <span class="mt-2 flex flex-wrap items-center gap-2 text-xs text-muted">
                  <StatusBadge
                    v-if="child.status"
                    :status="child.status"
                    :overdue="child.end_overdue"
                  />
                  {{ formatDateRange(child.start_date, child.end_date) }}
                </span>
              </RouterLink>
            </li>
            <li v-if="!byTemporal[key].length" class="px-1 py-2 text-sm text-muted">—</li>
          </ul>
        </div>
      </div>
    </section>
  </div>
</template>
