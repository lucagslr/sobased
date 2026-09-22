<script setup lang="ts">
/**
 * "Activité" tab (SPEC §14): who did what, when, on which object of the
 * project, newest first and grouped by day. Editors and up; the API hides
 * money entries from readers without the finance flag.
 */
import { History } from 'lucide-vue-next'
import { computed, ref, watch } from 'vue'

import { type ActivityEntry, type ActivityVerb, activityApi } from '@/api/activity'
import type { Project } from '@/api/projects'
import AppAvatar from '@/components/ui/AppAvatar.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import BaseSelect from '@/components/ui/BaseSelect.vue'
import BaseSwitch from '@/components/ui/BaseSwitch.vue'
import EmptyState from '@/components/ui/EmptyState.vue'
import SkeletonBlock from '@/components/ui/SkeletonBlock.vue'
import { describeChanges, groupByDay, sentence, VERB_LABELS, VERB_ORDER } from '@/utils/activity'
import { atLeast } from '@/utils/roles'

const props = defineProps<{ project: Project }>()

const entries = ref<ActivityEntry[] | null>(null)
const total = ref(0)
const page = ref(1)
const loadingMore = ref(false)
const includeDescendants = ref(false)
const verb = ref<ActivityVerb | ''>('')

const canSee = computed(() => atLeast(props.project.my_role, 'editor'))
const groups = computed(() => groupByDay(entries.value ?? []))
const hasMore = computed(() => (entries.value?.length ?? 0) < total.value)
const verbOptions = [
  { value: '', label: 'Toutes les actions' },
  ...VERB_ORDER.map((value) => ({ value, label: VERB_LABELS[value] })),
]

async function load() {
  if (!canSee.value) return
  page.value = 1
  const result = await activityApi.list({
    project: props.project.id,
    include_descendants: includeDescendants.value,
    verb: verb.value,
  })
  entries.value = result.results
  total.value = result.count
}

async function loadMore() {
  loadingMore.value = true
  try {
    page.value += 1
    const result = await activityApi.list({
      project: props.project.id,
      include_descendants: includeDescendants.value,
      verb: verb.value,
      page: page.value,
    })
    entries.value = [...(entries.value ?? []), ...result.results]
    total.value = result.count
  } finally {
    loadingMore.value = false
  }
}

/** The changed fields, except when the sentence already says it all. */
function details(entry: ActivityEntry): string[] {
  const changes = (entry.changes ?? {}) as Record<string, unknown>
  if ('version' in changes || 'parent' in changes || 'owner' in changes) return []
  return describeChanges(entry)
}

function time(iso: string): string {
  const date = new Date(iso)
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${pad(date.getHours())}:${pad(date.getMinutes())}`
}

watch([() => props.project.id, includeDescendants, verb], load, { immediate: true })
</script>

<template>
  <div v-if="!canSee" class="text-sm text-muted">
    Le journal d'activité est réservé aux éditeurs du projet.
  </div>
  <template v-else>
    <div class="mb-4 flex flex-wrap items-end gap-3">
      <BaseSelect v-model="verb" label="Action" :options="verbOptions" class="w-full sm:w-56" />
      <BaseSwitch
        v-if="project.depth < 4"
        v-model="includeDescendants"
        label="Avec les sous-projets"
        class="pb-2 sm:ml-auto"
      />
    </div>

    <div v-if="entries === null" class="space-y-2">
      <SkeletonBlock v-for="n in 5" :key="n" class="h-12" />
    </div>
    <EmptyState
      v-else-if="!entries.length"
      :icon="History"
      title="Rien dans le journal"
      text="Créations, modifications des champs clés, statuts, suppressions, partages et droits apparaîtront ici pendant 12 mois."
    />
    <div v-else class="space-y-6">
      <section v-for="group in groups" :key="group.day">
        <h3 class="mb-2 text-xs font-semibold tracking-wide text-muted uppercase">
          {{ group.day }}
        </h3>
        <ol class="divide-y divide-line rounded-xl border border-line bg-surface">
          <li v-for="entry in group.entries" :key="entry.id" class="flex gap-3 px-3 py-2.5">
            <AppAvatar
              :name="entry.actor?.display_name ?? 'Utilisateur supprimé'"
              :src="entry.actor?.avatar_url"
              :size="28"
            />
            <div class="min-w-0 flex-1">
              <p class="text-sm">
                {{ sentence(entry) }}
                <span
                  v-if="includeDescendants && entry.project_name && entry.project !== project.id"
                  class="text-muted"
                >
                  · {{ entry.project_name }}
                </span>
              </p>
              <ul v-if="details(entry).length" class="mt-0.5 space-y-0.5 text-xs text-muted">
                <li v-for="line in details(entry)" :key="line" class="truncate">
                  {{ line }}
                </li>
              </ul>
            </div>
            <time :datetime="entry.created_at" class="shrink-0 text-xs text-muted">
              {{ time(entry.created_at) }}
            </time>
          </li>
        </ol>
      </section>
      <div v-if="hasMore" class="text-center">
        <BaseButton variant="secondary" size="sm" :loading="loadingMore" @click="loadMore">
          Charger la suite
        </BaseButton>
      </div>
    </div>
  </template>
</template>
