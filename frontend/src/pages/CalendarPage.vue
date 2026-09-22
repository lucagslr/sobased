<script setup lang="ts">
/**
 * Global calendar (SPEC §15, page 4): month, week, day, agenda.
 * Today it shows the tasks of the selected workspace (or of all of them);
 * events join in phase 6 and external calendars in phase 11, in the same
 * TaskCalendarView component.
 *
 * Only the period on screen is loaded (`window_start` / `window_end`): a
 * calendar shows EVERY occurrence of recurring tasks, which adds up quickly.
 */
import { computed, ref, watch } from 'vue'

import { ApiError } from '@/api/client'
import { type Task, tasksApi } from '@/api/tasks'
import WorkspaceSwitcher from '@/components/layout/WorkspaceSwitcher.vue'
import WorkspaceFormPanel from '@/components/projects/WorkspaceFormPanel.vue'
import TaskCalendarView from '@/components/tasks/TaskCalendarView.vue'
import TaskPanel from '@/components/tasks/TaskPanel.vue'
import BaseSwitch from '@/components/ui/BaseSwitch.vue'
import PageHeader from '@/components/ui/PageHeader.vue'
import { useTaskPanel } from '@/composables/useTaskPanel'
import { useProjectsStore } from '@/stores/projects'
import { useUiStore } from '@/stores/ui'
import { useWorkspacesStore } from '@/stores/workspaces'
import { atLeast } from '@/utils/roles'

const ONLY_MINE_KEY = 'sobased-calendar-only-mine'

const projects = useProjectsStore()
const workspaces = useWorkspacesStore()
const ui = useUiStore()
const { taskId, openTask, closeTask } = useTaskPanel()

const tasks = ref<Task[]>([])
const period = ref<{ start: Date; end: Date } | null>(null)
const onlyMine = ref(readOnlyMine())
const workspacePanel = ref(false)
let request: AbortController | null = null

function readOnlyMine(): boolean {
  try {
    return localStorage.getItem(ONLY_MINE_KEY) === '1'
  } catch {
    return false
  }
}

/** One day of margin on each side: all-day dates are stored in UTC while the
 * period comes in local time. */
function padded(date: Date, days: number): string {
  const copy = new Date(date)
  copy.setDate(copy.getDate() + days)
  return copy.toISOString()
}

async function load() {
  if (!period.value) return
  request?.abort()
  request = new AbortController()
  try {
    tasks.value = await tasksApi.listAll(
      {
        window_start: padded(period.value.start, -1),
        window_end: padded(period.value.end, 1),
        workspace: workspaces.selection === 'all' ? undefined : workspaces.selection,
        assignee: onlyMine.value ? 'me' : undefined,
      },
      request.signal,
    )
  } catch (error) {
    if ((error as Error).name === 'AbortError') return // replaced by a newer request
    ui.toast(
      error instanceof ApiError ? error.message : "Le calendrier n'a pas pu être chargé.",
      'error',
    )
  }
}

function onRange(start: Date, end: Date) {
  period.value = { start, end }
}
watch([period, () => workspaces.selection, onlyMine], load)
watch(onlyMine, (value) => {
  try {
    localStorage.setItem(ONLY_MINE_KEY, value ? '1' : '0')
  } catch {
    /* private browsing: not remembered */
  }
})

function canReschedule(task: Task): boolean {
  return atLeast(projects.byId.get(task.project)?.my_role, 'editor')
}

const panelOpen = computed({
  get: () => taskId.value !== null,
  set: (value) => !value && closeTask(),
})
</script>

<template>
  <PageHeader
    title="Calendrier"
    :subtitle="workspaces.current ? workspaces.current.name : 'Tous les espaces'"
  >
    <BaseSwitch v-model="onlyMine" label="Seulement mes tâches" />
  </PageHeader>

  <!-- Below 1024px there is no sidebar: the workspace filter lives here. -->
  <div class="mb-5 lg:hidden">
    <WorkspaceSwitcher @create="workspacePanel = true" />
  </div>

  <TaskCalendarView
    :tasks="tasks"
    :can-move="canReschedule"
    @open="openTask($event.id)"
    @range="onRange"
    @changed="load"
  />

  <TaskPanel v-model:open="panelOpen" :task-id="taskId" @changed="load" />
  <WorkspaceFormPanel v-model:open="workspacePanel" />
</template>
