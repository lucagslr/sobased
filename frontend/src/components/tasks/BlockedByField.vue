<script setup lang="ts">
/**
 * The single "Bloquée par" field (SPEC §7: no clutter). Chips for the current
 * blockers and one search box; the server only proposes tasks of the same
 * root project that I can see and that would not create a loop.
 */
import { useDebounceFn } from '@vueuse/core'
import { Lock, X } from 'lucide-vue-next'
import { ref, watch } from 'vue'

import { type Blocker, type BlockerCandidate, tasksApi } from '@/api/tasks'
import { TASK_STATUS_LABELS } from '@/utils/tasks'

const props = defineProps<{ taskId: number; disabled?: boolean }>()
/** Blockers currently selected (details for display). */
const blockers = defineModel<Blocker[]>({ required: true })

const search = ref('')
const candidates = ref<BlockerCandidate[]>([])
const open = ref(false)
let controller: AbortController | null = null

const lookup = useDebounceFn(async () => {
  controller?.abort()
  controller = new AbortController()
  try {
    const found = await tasksApi.blockerCandidates(
      props.taskId,
      search.value.trim(),
      controller.signal,
    )
    const chosen = new Set(blockers.value.map((blocker) => blocker.id))
    candidates.value = found.filter((candidate) => !chosen.has(candidate.id))
  } catch {
    candidates.value = []
  }
}, 200)

watch(search, lookup)

function add(candidate: BlockerCandidate) {
  blockers.value = [
    ...blockers.value,
    {
      id: candidate.id,
      visible: true,
      title: candidate.title,
      status: candidate.status,
      project_name: candidate.project_name,
      is_open: candidate.status !== 'done' && candidate.status !== 'cancelled',
    },
  ]
  search.value = ''
  open.value = false
}

function remove(id: number) {
  blockers.value = blockers.value.filter((blocker) => blocker.id !== id)
}
</script>

<template>
  <div>
    <p class="mb-1.5 text-sm font-medium">Bloquée par</p>
    <ul v-if="blockers.length" class="mb-2 space-y-1">
      <li
        v-for="blocker in blockers"
        :key="blocker.id"
        class="flex items-center gap-2 rounded-lg border border-line px-2.5 py-1.5 text-sm"
      >
        <Lock
          class="size-3.5 shrink-0"
          :class="blocker.is_open ? 'text-fg' : 'text-muted opacity-40'"
          aria-hidden="true"
        />
        <span
          class="min-w-0 flex-1 truncate"
          :class="blocker.is_open ? '' : 'text-muted line-through'"
        >
          {{ blocker.visible ? blocker.title : "Tâche d'un autre projet" }}
        </span>
        <span v-if="blocker.visible && blocker.status" class="shrink-0 text-xs text-muted">
          {{ blocker.project_name }} · {{ TASK_STATUS_LABELS[blocker.status] }}
        </span>
        <button
          v-if="!disabled"
          type="button"
          class="rounded p-0.5 text-muted hover:text-danger"
          aria-label="Retirer ce bloqueur"
          @click="remove(blocker.id)"
        >
          <X class="size-3.5" aria-hidden="true" />
        </button>
      </li>
    </ul>
    <div v-if="!disabled" class="relative">
      <input
        v-model="search"
        type="text"
        placeholder="Chercher une tâche du même projet…"
        aria-label="Chercher une tâche bloquante"
        class="h-9 w-full rounded-lg border border-line bg-surface px-3 text-sm placeholder:text-muted"
        @focus="((open = true), lookup())"
        @keydown.esc="open = false"
      />
      <ul
        v-if="open && candidates.length"
        class="absolute z-10 mt-1 max-h-56 w-full overflow-y-auto rounded-xl border border-line bg-surface shadow-lg"
      >
        <li v-for="candidate in candidates" :key="candidate.id">
          <button
            type="button"
            class="flex w-full items-baseline gap-2 px-3 py-2 text-left text-sm hover:bg-surface-2"
            @click="add(candidate)"
          >
            <span class="min-w-0 flex-1 truncate">{{ candidate.title }}</span>
            <span class="shrink-0 text-xs text-muted">{{ candidate.project_name }}</span>
          </button>
        </li>
      </ul>
    </div>
    <p v-else-if="!blockers.length" class="text-sm text-muted">Aucune dépendance.</p>
  </div>
</template>
