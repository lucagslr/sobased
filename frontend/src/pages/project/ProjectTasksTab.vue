<script setup lang="ts">
/**
 * Tasks of a project, list view. Kanban, calendar and Gantt views (with the
 * view switcher remembered per project) arrive in phase 5.
 */
import { CircleCheckBig, Plus } from 'lucide-vue-next'
import { computed, ref, watch } from 'vue'

import { ApiError } from '@/api/client'
import type { Project } from '@/api/projects'
import { type Task, tasksApi } from '@/api/tasks'
import TaskPanel from '@/components/tasks/TaskPanel.vue'
import TaskRow from '@/components/tasks/TaskRow.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import EmptyState from '@/components/ui/EmptyState.vue'
import SkeletonBlock from '@/components/ui/SkeletonBlock.vue'
import { useTaskPanel } from '@/composables/useTaskPanel'
import { useAuthStore } from '@/stores/auth'
import { useProjectsStore } from '@/stores/projects'
import { useUiStore } from '@/stores/ui'
import { atLeast } from '@/utils/roles'
import { CLOSED_STATUSES, collapseSeries, compareTasks } from '@/utils/tasks'

const props = defineProps<{ project: Project }>()

const auth = useAuthStore()
const projects = useProjectsStore()
const ui = useUiStore()
const { taskId, openTask, closeTask } = useTaskPanel()

const tasks = ref<Task[] | null>(null)
const includeChildren = ref(true)
const showClosed = ref(false)
const creating = ref(false)
const quickTitle = ref('')

const canEdit = computed(() => atLeast(props.project.my_role, 'editor'))
const hasChildren = computed(() => projects.childrenOf(props.project.id).length > 0)
// Recurring series show their late occurrences and the next one, not all 13.
const openTasks = computed(() =>
  collapseSeries((tasks.value ?? []).filter((t) => !CLOSED_STATUSES.includes(t.status))).sort(
    compareTasks,
  ),
)
const closedTasks = computed(() =>
  (tasks.value ?? []).filter((t) => CLOSED_STATUSES.includes(t.status)),
)

async function load() {
  const page = await tasksApi.list({
    project: props.project.id,
    include_descendants: includeChildren.value,
  })
  tasks.value = page.results
}
watch(() => [props.project.id, includeChildren.value], load, { immediate: true })

// Editors tick any task; an assigned commenter ticks their own (decision D6).
function canComplete(task: Task): boolean {
  if (canEdit.value) return true
  const mine = task.assignees.some((user) => user.username === auth.user?.username)
  return mine && atLeast(props.project.my_role, 'commenter')
}

async function toggleDone(task: Task) {
  try {
    await tasksApi.update(task.id, { status: task.status === 'done' ? 'todo' : 'done' })
    await load()
  } catch (error) {
    ui.toast(error instanceof ApiError ? error.message : 'Le statut est resté inchangé.', 'error')
  }
}

async function quickAdd() {
  const title = quickTitle.value.trim()
  if (!title) return
  try {
    await tasksApi.create({ project: props.project.id, title })
    quickTitle.value = ''
    await load()
  } catch (error) {
    ui.toast(error instanceof ApiError ? error.message : "La tâche n'a pas été créée.", 'error')
  }
}

const panelOpen = computed({
  get: () => taskId.value !== null || creating.value,
  set: (value) => {
    if (value) return
    creating.value = false
    if (taskId.value !== null) closeTask()
  },
})
</script>

<template>
  <div class="mb-4 flex flex-wrap items-center gap-3">
    <form v-if="canEdit" class="flex min-w-0 flex-1 gap-2" @submit.prevent="quickAdd">
      <input
        v-model="quickTitle"
        type="text"
        maxlength="240"
        placeholder="Nouvelle tâche…"
        aria-label="Titre de la nouvelle tâche"
        class="h-10 min-w-0 flex-1 rounded-lg border border-line bg-surface px-3 text-[15px] placeholder:text-muted"
      />
      <!-- A real submit button: Enter works everywhere, and phones get a target. -->
      <BaseButton type="submit" :disabled="!quickTitle.trim()">
        <Plus class="size-4" aria-hidden="true" />
        <span class="hidden sm:inline">Ajouter</span>
      </BaseButton>
      <BaseButton variant="secondary" @click="creating = true">Détaillée</BaseButton>
    </form>
    <label v-if="hasChildren" class="flex items-center gap-2 text-sm text-muted">
      <input v-model="includeChildren" type="checkbox" class="size-4" />
      Inclure les sous-projets
    </label>
  </div>

  <div v-if="tasks === null" class="space-y-2">
    <SkeletonBlock v-for="n in 4" :key="n" class="h-14 w-full" />
  </div>

  <EmptyState
    v-else-if="!tasks.length"
    :icon="CircleCheckBig"
    title="Aucune tâche"
    :text="
      canEdit
        ? 'Écris un titre ci-dessus pour créer la première.'
        : 'Personne n\'a encore créé de tâche dans ce projet.'
    "
  />

  <template v-else>
    <ul class="border-t border-line">
      <TaskRow
        v-for="task in openTasks"
        :key="task.id"
        :task="task"
        :show-project="includeChildren && task.project !== project.id"
        :can-complete="canComplete(task)"
        @open="openTask(task.id)"
        @toggle-done="toggleDone(task)"
      />
    </ul>
    <p v-if="!openTasks.length" class="py-6 text-sm text-muted">Tout est terminé ici.</p>

    <div v-if="closedTasks.length" class="mt-6">
      <button
        type="button"
        class="text-sm font-medium text-muted hover:text-fg"
        :aria-expanded="showClosed"
        @click="showClosed = !showClosed"
      >
        {{ showClosed ? 'Masquer' : 'Afficher' }} les {{ closedTasks.length }} tâche{{
          closedTasks.length > 1 ? 's' : ''
        }}
        terminée{{ closedTasks.length > 1 ? 's' : '' }} ou annulée{{
          closedTasks.length > 1 ? 's' : ''
        }}
      </button>
      <ul v-if="showClosed" class="mt-2 border-t border-line">
        <TaskRow
          v-for="task in closedTasks"
          :key="task.id"
          :task="task"
          :can-complete="canComplete(task)"
          @open="openTask(task.id)"
          @toggle-done="toggleDone(task)"
        />
      </ul>
    </div>
  </template>

  <TaskPanel
    v-model:open="panelOpen"
    :task-id="taskId"
    :create-in="creating ? project.id : null"
    @changed="load"
    @created="((creating = false), openTask($event.id))"
  />
</template>
