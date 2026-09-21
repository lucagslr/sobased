<script setup lang="ts">
/**
 * "Mes tâches" (SPEC §15): everything assigned to me and still open, grouped
 * En retard / Aujourd'hui / Demain / Cette semaine / Plus tard / Sans date.
 * Overdue comes first and stays red until someone acts: nothing is postponed.
 */
import { CircleCheckBig } from 'lucide-vue-next'
import { computed, onMounted, ref } from 'vue'

import { ApiError } from '@/api/client'
import { type Task, tasksApi } from '@/api/tasks'
import TaskPanel from '@/components/tasks/TaskPanel.vue'
import TaskRow from '@/components/tasks/TaskRow.vue'
import EmptyState from '@/components/ui/EmptyState.vue'
import PageHeader from '@/components/ui/PageHeader.vue'
import SkeletonBlock from '@/components/ui/SkeletonBlock.vue'
import { useTaskPanel } from '@/composables/useTaskPanel'
import { useUiStore } from '@/stores/ui'
import { useWorkspacesStore } from '@/stores/workspaces'
import { useProjectsStore } from '@/stores/projects'
import { atLeast } from '@/utils/roles'
import {
  collapseSeries,
  compareTasks,
  groupTasks,
  TASK_GROUP_LABELS,
  TASK_GROUP_ORDER,
} from '@/utils/tasks'

const ui = useUiStore()
const workspaces = useWorkspacesStore()
const projects = useProjectsStore()
const { taskId, openTask, closeTask } = useTaskPanel()
const tasks = ref<Task[] | null>(null)

async function load() {
  const page = await tasksApi.list({ assignee: 'me', open: true })
  tasks.value = page.results
}
onMounted(load)

// The workspace chosen in the sidebar filters this page too.
const visible = computed(() => {
  const selection = workspaces.selection
  const all = tasks.value ?? []
  if (selection === 'all') return all
  return all.filter((task) => projects.byId.get(task.project)?.workspace === selection)
})
const groups = computed(() => {
  const grouped = groupTasks(collapseSeries(visible.value))
  for (const key of TASK_GROUP_ORDER) grouped[key].sort(compareTasks)
  return grouped
})

// I am the assignee of all of these: ticking needs the Commenter role (D6).
function canComplete(task: Task): boolean {
  return atLeast(projects.byId.get(task.project)?.my_role, 'commenter')
}

async function toggleDone(task: Task) {
  try {
    await tasksApi.update(task.id, { status: 'done' })
    await load()
  } catch (error) {
    ui.toast(error instanceof ApiError ? error.message : 'Le statut est resté inchangé.', 'error')
  }
}

const panelOpen = computed({
  get: () => taskId.value !== null,
  set: (value) => !value && closeTask(),
})
</script>

<template>
  <PageHeader
    title="Mes tâches"
    :subtitle="workspaces.current ? workspaces.current.name : 'Tous les espaces'"
  />

  <div v-if="tasks === null" class="space-y-2">
    <SkeletonBlock v-for="n in 5" :key="n" class="h-14 w-full" />
  </div>

  <EmptyState
    v-else-if="!visible.length"
    :icon="CircleCheckBig"
    title="Rien à faire pour l'instant"
    text="Les tâches qu'on t'assigne, dans n'importe quel projet, apparaîtront ici."
  />

  <div v-else class="space-y-8">
    <template v-for="key in TASK_GROUP_ORDER" :key="key">
      <section v-if="groups[key].length" :aria-labelledby="`group-${key}`">
        <h2
          :id="`group-${key}`"
          class="mb-1 flex items-center gap-2 text-sm font-semibold"
          :class="key === 'overdue' ? 'text-danger' : ''"
        >
          {{ TASK_GROUP_LABELS[key] }}
          <span class="font-normal text-muted">{{ groups[key].length }}</span>
        </h2>
        <ul class="border-t border-line">
          <TaskRow
            v-for="task in groups[key]"
            :key="task.id"
            :task="task"
            show-project
            :can-complete="canComplete(task)"
            @open="openTask(task.id)"
            @toggle-done="toggleDone(task)"
          />
        </ul>
      </section>
    </template>
  </div>

  <TaskPanel v-model:open="panelOpen" :task-id="taskId" @changed="load" />
</template>
