<script setup lang="ts">
/**
 * "Calendrier" tab of a project: its tasks AND its events on one calendar
 * (the Tâches tab has a calendar of tasks only). Clicking an empty day
 * proposes a new RDV: a calendar is where meetings get planned.
 */
import { computed, defineAsyncComponent, ref, watch } from 'vue'

import { ApiError } from '@/api/client'
import { type Event, eventsApi } from '@/api/events'
import type { Project } from '@/api/projects'
import { type Task, tasksApi } from '@/api/tasks'
import EventPanel from '@/components/events/EventPanel.vue'
import TaskPanel from '@/components/tasks/TaskPanel.vue'
import { useEventPanel } from '@/composables/useEventPanel'
import { useTaskPanel } from '@/composables/useTaskPanel'
import { useProjectsStore } from '@/stores/projects'
import { useUiStore } from '@/stores/ui'
import { atLeast } from '@/utils/roles'

const TaskCalendarView = defineAsyncComponent(
  () => import('@/components/tasks/TaskCalendarView.vue'),
)

const props = defineProps<{ project: Project }>()

const projects = useProjectsStore()
const ui = useUiStore()
const { eventId, openEvent, closeEvent } = useEventPanel()
const { taskId, openTask, closeTask } = useTaskPanel()

const tasks = ref<Task[]>([])
const events = ref<Event[]>([])
const period = ref<{ start: Date; end: Date } | null>(null)
const createStart = ref<string | null>(null)
const taskFromEvent = ref<Event | null>(null)
let request: AbortController | null = null

const canEdit = computed(() => atLeast(props.project.my_role, 'editor'))

function padded(date: Date, days: number): string {
  const copy = new Date(date)
  copy.setDate(copy.getDate() + days)
  return copy.toISOString()
}

async function load() {
  if (!period.value) return
  request?.abort()
  request = new AbortController()
  const filters = {
    project: props.project.id,
    include_descendants: true,
    window_start: padded(period.value.start, -1),
    window_end: padded(period.value.end, 1),
  }
  try {
    ;[tasks.value, events.value] = await Promise.all([
      tasksApi.listAll(filters, request.signal),
      eventsApi.listAll(filters, request.signal),
    ])
  } catch (error) {
    if ((error as Error).name === 'AbortError') return
    ui.toast(
      error instanceof ApiError ? error.message : "Le calendrier n'a pas pu être chargé.",
      'error',
    )
  }
}
watch([period, () => props.project.id], load)

function roleOn(projectId: number) {
  return projects.byId.get(projectId)?.my_role ?? props.project.my_role
}
const canMoveTask = (task: Task) => atLeast(roleOn(task.project), 'editor')
const canMoveEvent = (event: Event) => atLeast(roleOn(event.project), 'editor')

function createTaskFrom(event: Event) {
  taskFromEvent.value = event
  closeEvent()
}

const eventPanelOpen = computed({
  get: () => eventId.value !== null || createStart.value !== null,
  set: (value) => {
    if (value) return
    createStart.value = null
    if (eventId.value !== null) closeEvent()
  },
})
const taskPanelOpen = computed({
  get: () => taskId.value !== null || taskFromEvent.value !== null,
  set: (value) => {
    if (value) return
    taskFromEvent.value = null
    if (taskId.value !== null) closeTask()
  },
})
</script>

<template>
  <TaskCalendarView
    :tasks="tasks"
    :events="events"
    :can-move="canMoveTask"
    :can-move-event="canMoveEvent"
    :can-create="canEdit"
    @open="openTask($event.id)"
    @open-event="openEvent($event.id)"
    @create="createStart = $event"
    @range="(start, end) => (period = { start, end })"
    @changed="load"
  />

  <EventPanel
    v-model:open="eventPanelOpen"
    :event-id="eventId"
    :create-in="createStart !== null ? project.id : null"
    :create-start="createStart"
    @changed="load"
    @created="((createStart = null), openEvent($event.id))"
    @create-task="createTaskFrom"
    @open-task="openTask"
  />
  <TaskPanel
    v-model:open="taskPanelOpen"
    :task-id="taskId"
    :create-in="taskFromEvent ? taskFromEvent.project : null"
    :create-from-event="taskFromEvent"
    @changed="load"
    @created="((taskFromEvent = null), openTask($event.id))"
    @open-event="openEvent"
  />
</template>
