<script setup lang="ts">
/**
 * Tasks of a project, in four views: Liste / Kanban / Calendrier / Gantt
 * (SPEC §15). The chosen view is remembered PER PROJECT, on the server, so it
 * follows the user from the laptop to the phone.
 *
 * The four views share one load of the tasks: switching is instant, and a
 * change made in one view is what the next one shows.
 */
import { useMediaQuery } from '@vueuse/core'
import {
  CalendarDays,
  CircleCheckBig,
  Columns3,
  GanttChartSquare,
  List,
  Plus,
} from 'lucide-vue-next'
import { computed, defineAsyncComponent, ref, watch } from 'vue'

import { ApiError } from '@/api/client'
import { type Project, projectsApi, type TasksView } from '@/api/projects'
import { type Task, tasksApi } from '@/api/tasks'
import TaskKanbanView from '@/components/tasks/TaskKanbanView.vue'
import TaskPanel from '@/components/tasks/TaskPanel.vue'
import TaskRow from '@/components/tasks/TaskRow.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import EmptyState from '@/components/ui/EmptyState.vue'
import SegmentedControl from '@/components/ui/SegmentedControl.vue'
import SkeletonBlock from '@/components/ui/SkeletonBlock.vue'
import { useTaskPanel } from '@/composables/useTaskPanel'
import { useAuthStore } from '@/stores/auth'
import { useProjectsStore } from '@/stores/projects'
import { useUiStore } from '@/stores/ui'
import { atLeast } from '@/utils/roles'
import { CLOSED_STATUSES, collapseSeries, compareTasks } from '@/utils/tasks'

// FullCalendar and frappe-gantt are heavy: only fetched when their view is used.
const TaskCalendarView = defineAsyncComponent(
  () => import('@/components/tasks/TaskCalendarView.vue'),
)
const TaskGanttView = defineAsyncComponent(() => import('@/components/tasks/TaskGanttView.vue'))

const props = defineProps<{ project: Project }>()

const auth = useAuthStore()
const projects = useProjectsStore()
const ui = useUiStore()
const { taskId, openTask, closeTask } = useTaskPanel()

const VIEWS: { value: TasksView; label: string; icon: typeof List }[] = [
  { value: 'list', label: 'Liste', icon: List },
  { value: 'kanban', label: 'Kanban', icon: Columns3 },
  { value: 'calendar', label: 'Calendrier', icon: CalendarDays },
  { value: 'gantt', label: 'Gantt', icon: GanttChartSquare },
]
const phone = useMediaQuery('(max-width: 639px)')

const tasks = ref<Task[] | null>(null)
const view = ref<TasksView>(rememberedView())
const includeChildren = ref(true)
const showClosed = ref(false)
const creating = ref(false)
const createDue = ref<string | null>(null)
const quickTitle = ref('')

const canEdit = computed(() => atLeast(props.project.my_role, 'editor'))
const hasChildren = computed(() => projects.childrenOf(props.project.id).length > 0)
// Recurring series show their late occurrences and the next one, not all 13.
// The calendar is the exception: it shows every occurrence.
const openTasks = computed(() =>
  collapseSeries((tasks.value ?? []).filter((t) => !CLOSED_STATUSES.includes(t.status))).sort(
    compareTasks,
  ),
)
const closedTasks = computed(() =>
  (tasks.value ?? []).filter((t) => CLOSED_STATUSES.includes(t.status)),
)
const boardTasks = computed(() => [...openTasks.value, ...closedTasks.value])
const ganttTasks = computed(() => boardTasks.value.filter((t) => t.status !== 'cancelled'))

async function load() {
  tasks.value = await tasksApi.listAll({
    project: props.project.id,
    include_descendants: includeChildren.value,
  })
}
watch(() => [props.project.id, includeChildren.value], load, { immediate: true })

watch(
  () => props.project.id,
  () => (view.value = rememberedView()),
)
/** The project object was loaded when the page opened: a view chosen since
 * then (before visiting another tab of the page) is more recent. */
function rememberedView(): TasksView {
  return projects.tasksViews.get(props.project.id) ?? props.project.my_tasks_view
}
function chooseView(chosen: TasksView) {
  view.value = chosen
  projects.tasksViews.set(props.project.id, chosen)
  // A preference, not data: if saving fails the view still works.
  projectsApi.setMyState(props.project.id, chosen).catch(() => undefined)
}

function roleOn(task: Task) {
  return projects.byId.get(task.project)?.my_role ?? props.project.my_role
}
/** Dates (calendar, Gantt): editors of the task's project only. */
function canReschedule(task: Task): boolean {
  return atLeast(roleOn(task), 'editor')
}
/** Status (list tick, kanban): editors, and the assignee as commenter (D6). */
function canComplete(task: Task): boolean {
  if (canReschedule(task)) return true
  const mine = task.assignees.some((user) => user.username === auth.user?.username)
  return mine && atLeast(roleOn(task), 'commenter')
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

function startCreating(dueKey: string | null = null) {
  createDue.value = dueKey
  creating.value = true
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
    <SegmentedControl
      :model-value="view"
      label="Vue des tâches"
      :options="VIEWS"
      :hide-labels="phone"
      @update:model-value="chooseView"
    />
    <label v-if="hasChildren" class="flex items-center gap-2 text-sm text-muted">
      <input v-model="includeChildren" type="checkbox" class="size-4" />
      Inclure les sous-projets
    </label>
  </div>

  <form v-if="canEdit" class="mb-4 flex min-w-0 gap-2" @submit.prevent="quickAdd">
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
    <BaseButton variant="secondary" @click="startCreating()">Détaillée</BaseButton>
  </form>

  <div v-if="tasks === null" class="space-y-2">
    <SkeletonBlock v-for="n in 4" :key="n" class="h-14 w-full" />
  </div>

  <EmptyState
    v-else-if="!tasks.length && view !== 'calendar'"
    :icon="CircleCheckBig"
    title="Aucune tâche"
    :text="
      canEdit
        ? 'Écris un titre ci-dessus pour créer la première.'
        : 'Personne n\'a encore créé de tâche dans ce projet.'
    "
  />

  <template v-else-if="view === 'list'">
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

  <TaskKanbanView
    v-else-if="view === 'kanban'"
    :tasks="boardTasks"
    :project-id="project.id"
    :can-move="canComplete"
    @open="openTask($event.id)"
    @changed="load"
  />

  <TaskCalendarView
    v-else-if="view === 'calendar'"
    :tasks="tasks"
    :can-move="canReschedule"
    :can-create="canEdit"
    @open="openTask($event.id)"
    @create="startCreating"
    @changed="load"
  />

  <TaskGanttView
    v-else
    :tasks="ganttTasks"
    :can-move="canReschedule"
    @open="openTask($event.id)"
    @changed="load"
  />

  <TaskPanel
    v-model:open="panelOpen"
    :task-id="taskId"
    :create-in="creating ? project.id : null"
    :create-due="createDue"
    @changed="load"
    @created="((creating = false), openTask($event.id))"
  />
</template>
