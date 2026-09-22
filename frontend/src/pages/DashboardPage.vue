<script setup lang="ts">
/**
 * Global dashboard (SPEC §15, page 1): a grid of widgets that can be moved,
 * resized and hidden, per saved view. "En retard" is always first and red.
 *
 * Layout model (decision D3): widgets flow in a 1 / 2 / 3 column grid; each
 * one has a width of 1 to 3 columns and a normal or double height. Dragging
 * only changes the ORDER. Everything is saved on the server, per view.
 *
 * `force-fallback`: SortableJS then drags with pointer events instead of the
 * native HTML5 drag-and-drop, which behaves the same with a mouse and a finger.
 */
import { Pencil, Plus, SlidersHorizontal } from 'lucide-vue-next'
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import draggable from 'vuedraggable'

import { ApiError } from '@/api/client'
import type { DashboardView, ValidateItem, WidgetLayout } from '@/api/dashboard'
import type { Event } from '@/api/events'
import { type PinnedItem, type Task, tasksApi } from '@/api/tasks'
import DashboardViewPanel from '@/components/dashboard/DashboardViewPanel.vue'
import MeetingsWidget from '@/components/dashboard/MeetingsWidget.vue'
import PinnedTodosWidget from '@/components/dashboard/PinnedTodosWidget.vue'
import TaskListWidget from '@/components/dashboard/TaskListWidget.vue'
import ToValidateWidget from '@/components/dashboard/ToValidateWidget.vue'
import WidgetFrame from '@/components/dashboard/WidgetFrame.vue'
import EventPanel from '@/components/events/EventPanel.vue'
import TaskPanel from '@/components/tasks/TaskPanel.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import PageHeader from '@/components/ui/PageHeader.vue'
import SkeletonBlock from '@/components/ui/SkeletonBlock.vue'
import { useEventPanel } from '@/composables/useEventPanel'
import { useTaskPanel } from '@/composables/useTaskPanel'
import { useAuthStore } from '@/stores/auth'
import { useDashboardStore } from '@/stores/dashboard'
import { useUiStore } from '@/stores/ui'
import { LOCKED_WIDGET, patchWidget, reorder, sizeClass, widgetsToShow } from '@/utils/dashboard'

const auth = useAuthStore()
const dashboard = useDashboardStore()
const ui = useUiStore()
const router = useRouter()
const { taskId, openTask, closeTask } = useTaskPanel()
const { eventId, openEvent, closeEvent } = useEventPanel()

const editing = ref(false)
// "Créer une tâche depuis ce RDV", from the meetings widget.
const taskFromEvent = ref<Event | null>(null)
const viewPanel = ref(false)
const viewBeingEdited = ref<DashboardView | null>(null)

const firstName = computed(() => auth.user?.first_name || auth.user?.username || '')
const today = new Intl.DateTimeFormat('fr-CH', { dateStyle: 'full' }).format(new Date())
const widgets = computed(() => dashboard.summary?.widgets ?? null)
const layout = computed(() => dashboard.current?.layout ?? [])
const shown = computed(() => widgetsToShow(layout.value, widgets.value, editing.value))
const locked = computed(() => shown.value.find((item) => item.key === LOCKED_WIDGET))

// vuedraggable works on a list it can reorder: every widget but the locked one.
const movable = computed<WidgetLayout[]>({
  get: () => shown.value.filter((item) => item.key !== LOCKED_WIDGET),
  set: (moved) => dashboard.setLayout(reorder(layout.value, moved)),
})

onMounted(() => dashboard.init())

function change(item: WidgetLayout, patch: Partial<Omit<WidgetLayout, 'key'>>) {
  dashboard.setLayout(patchWidget(layout.value, item.key, patch))
}

function countOf(item: WidgetLayout): number {
  return widgets.value?.[item.key].count ?? 0
}

function editView(view: DashboardView | null) {
  viewBeingEdited.value = view
  viewPanel.value = true
}

function fail(error: unknown, fallback: string) {
  ui.toast(error instanceof ApiError ? error.message : fallback, 'error')
}

async function toggleDone(task: Task) {
  try {
    await tasksApi.update(task.id, { status: task.status === 'done' ? 'todo' : 'done' })
    await dashboard.loadSummary()
  } catch (error) {
    fail(error, 'Le statut est resté inchangé.')
  }
}

async function tick(item: PinnedItem) {
  try {
    await tasksApi.updateChecklistItem(item.id, { done: true })
    await dashboard.loadSummary()
  } catch (error) {
    fail(error, "L'élément n'a pas pu être coché.")
  }
}

function openValidation(item: ValidateItem) {
  if (item.kind === 'task') openTask(item.id)
  else router.push(`/projets/${item.project}`)
}

const panelOpen = computed({
  get: () => taskId.value !== null || taskFromEvent.value !== null,
  set: (value) => {
    if (value) return
    taskFromEvent.value = null
    if (taskId.value !== null) closeTask()
  },
})
const eventPanelOpen = computed({
  get: () => eventId.value !== null,
  set: (value) => !value && closeEvent(),
})

function createTaskFrom(event: Event) {
  taskFromEvent.value = event
  closeEvent()
}
</script>

<template>
  <PageHeader :title="`Salut ${firstName}`" :subtitle="today">
    <BaseButton
      :variant="editing ? 'primary' : 'secondary'"
      :aria-pressed="editing"
      @click="editing = !editing"
    >
      <SlidersHorizontal class="size-4" aria-hidden="true" />
      {{ editing ? 'Terminer' : 'Personnaliser' }}
    </BaseButton>
  </PageHeader>

  <!-- Saved views -->
  <nav
    class="no-scrollbar -mx-4 mb-5 flex items-center gap-1 overflow-x-auto px-4 sm:mx-0 sm:px-0"
    aria-label="Vues du dashboard"
  >
    <button
      v-for="view in dashboard.views"
      :key="view.id"
      type="button"
      class="group inline-flex h-9 shrink-0 items-center gap-1.5 rounded-lg px-3 text-sm font-medium transition-colors"
      :class="
        view.id === dashboard.currentId
          ? 'bg-surface-2 text-fg'
          : 'text-muted hover:bg-surface-2 hover:text-fg'
      "
      :aria-current="view.id === dashboard.currentId ? 'page' : undefined"
      @click="dashboard.select(view.id)"
    >
      {{ view.name }}
    </button>
    <button
      v-if="dashboard.current"
      type="button"
      class="flex size-9 shrink-0 items-center justify-center rounded-lg text-muted hover:bg-surface-2 hover:text-fg"
      :aria-label="`Modifier la vue ${dashboard.current.name}`"
      @click="editView(dashboard.current)"
    >
      <Pencil class="size-4" aria-hidden="true" />
    </button>
    <button
      type="button"
      class="flex size-9 shrink-0 items-center justify-center rounded-lg text-muted hover:bg-surface-2 hover:text-fg"
      aria-label="Nouvelle vue"
      @click="editView(null)"
    >
      <Plus class="size-4" aria-hidden="true" />
    </button>
  </nav>

  <p v-if="editing" class="mb-4 rounded-lg bg-surface-2 px-4 py-2.5 text-sm text-muted">
    Fais glisser un widget par sa poignée pour le déplacer ; change sa largeur, sa hauteur ou
    masque-le avec les boutons de son en-tête. « En retard » reste toujours en premier.
  </p>

  <div v-if="!dashboard.current" class="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
    <SkeletonBlock v-for="n in 5" :key="n" class="h-80" />
  </div>

  <draggable
    v-else
    v-model="movable"
    item-key="key"
    handle=".drag-handle"
    :disabled="!editing"
    :animation="180"
    :force-fallback="true"
    ghost-class="opacity-40"
    class="grid gap-4 md:grid-cols-2 xl:grid-cols-3"
  >
    <!-- Not draggable: rendered before the list, inside the same grid. -->
    <template v-if="locked" #header>
      <WidgetFrame
        :item="locked"
        :count="countOf(locked)"
        :editing="editing"
        :alert="countOf(locked) > 0"
        :class="sizeClass(locked.size)"
        @change="change(locked, $event)"
      >
        <TaskListWidget
          v-if="widgets"
          :tasks="widgets.overdue.items"
          :total="widgets.overdue.count"
          @open="openTask($event.id)"
          @toggle-done="toggleDone"
        />
      </WidgetFrame>
    </template>

    <template #item="{ element }: { element: WidgetLayout }">
      <WidgetFrame
        :item="element"
        :count="countOf(element)"
        :editing="editing"
        :class="sizeClass(element.size)"
        @change="change(element, $event)"
      >
        <template v-if="widgets">
          <TaskListWidget
            v-if="element.key === 'today' || element.key === 'next7'"
            :tasks="widgets[element.key].items"
            :total="widgets[element.key].count"
            @open="openTask($event.id)"
            @toggle-done="toggleDone"
          />
          <PinnedTodosWidget
            v-else-if="element.key === 'pinned'"
            :items="widgets.pinned.items"
            @tick="tick"
            @open="openTask($event.task)"
          />
          <ToValidateWidget
            v-else-if="element.key === 'to_validate'"
            :items="widgets.to_validate.items"
            @open="openValidation"
          />
          <MeetingsWidget
            v-else-if="element.key === 'meetings'"
            :events="widgets.meetings.items"
            :total="widgets.meetings.count"
            @open="openEvent($event.id)"
          />
        </template>
      </WidgetFrame>
    </template>
  </draggable>

  <DashboardViewPanel v-model:open="viewPanel" :view="viewBeingEdited" />
  <TaskPanel
    v-model:open="panelOpen"
    :task-id="taskId"
    :create-in="taskFromEvent ? taskFromEvent.project : null"
    :create-from-event="taskFromEvent"
    @changed="dashboard.loadSummary()"
    @created="((taskFromEvent = null), openTask($event.id))"
    @open-event="openEvent"
  />
  <EventPanel
    v-model:open="eventPanelOpen"
    :event-id="eventId"
    @changed="dashboard.loadSummary()"
    @create-task="createTaskFrom"
    @open-task="openTask"
  />
</template>
