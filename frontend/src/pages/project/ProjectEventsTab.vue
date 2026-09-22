<script setup lang="ts">
/**
 * "RDV" tab of a project: the agenda of its events (and its sub-projects'),
 * upcoming ones by month, past ones folded at the end. The panel is driven
 * by the URL (?rdv=42), like the task panel.
 */
import { CalendarClock, Plus } from 'lucide-vue-next'
import { computed, ref, watch } from 'vue'

import { type Event, eventsApi } from '@/api/events'
import type { Project } from '@/api/projects'
import EventPanel from '@/components/events/EventPanel.vue'
import EventRow from '@/components/events/EventRow.vue'
import TaskPanel from '@/components/tasks/TaskPanel.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import EmptyState from '@/components/ui/EmptyState.vue'
import SkeletonBlock from '@/components/ui/SkeletonBlock.vue'
import { useEventPanel } from '@/composables/useEventPanel'
import { useTaskPanel } from '@/composables/useTaskPanel'
import { useProjectsStore } from '@/stores/projects'
import { groupAgenda, monthLabel } from '@/utils/events'
import { atLeast } from '@/utils/roles'

const props = defineProps<{ project: Project }>()

const projects = useProjectsStore()
const { eventId, openEvent, closeEvent } = useEventPanel()
const { taskId, openTask, closeTask } = useTaskPanel()

const events = ref<Event[] | null>(null)
const includeChildren = ref(true)
const showPast = ref(false)
const creating = ref(false)
const taskFromEvent = ref<Event | null>(null)

const canEdit = computed(() => atLeast(props.project.my_role, 'editor'))
const hasChildren = computed(() => projects.childrenOf(props.project.id).length > 0)
const groups = computed(() => groupAgenda(events.value ?? []))
const upcoming = computed(() => groups.value.filter((group) => group.key !== 'past'))
const past = computed(() => groups.value.find((group) => group.key === 'past')?.items ?? [])

async function load() {
  events.value = await eventsApi.listAll({
    project: props.project.id,
    include_descendants: includeChildren.value,
  })
}
watch(() => [props.project.id, includeChildren.value], load, { immediate: true })

function createTaskFrom(event: Event) {
  taskFromEvent.value = event
  closeEvent()
}

const eventPanelOpen = computed({
  get: () => eventId.value !== null || creating.value,
  set: (value) => {
    if (value) return
    creating.value = false
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
  <div class="mb-4 flex flex-wrap items-center gap-3">
    <BaseButton v-if="canEdit" @click="creating = true">
      <Plus class="size-4" aria-hidden="true" /> Nouveau RDV
    </BaseButton>
    <label v-if="hasChildren" class="flex items-center gap-2 text-sm text-muted">
      <input v-model="includeChildren" type="checkbox" class="size-4" />
      Inclure les sous-projets
    </label>
  </div>

  <div v-if="events === null" class="space-y-2">
    <SkeletonBlock v-for="n in 4" :key="n" class="h-14 w-full" />
  </div>

  <EmptyState
    v-else-if="!events.length"
    :icon="CalendarClock"
    title="Aucun RDV"
    :text="
      canEdit
        ? 'Un RDV, une date live, un tournage, un cours : tout ce qui a lieu à un moment donné.'
        : 'Personne n\'a encore planifié de RDV dans ce projet.'
    "
  />

  <template v-else>
    <section v-for="group in upcoming" :key="group.key" class="mb-6">
      <h2 class="mb-1 text-sm font-semibold text-muted">{{ monthLabel(group.key) }}</h2>
      <ul class="border-t border-line">
        <EventRow
          v-for="event in group.items"
          :key="event.id"
          :event="event"
          :show-project="includeChildren && event.project !== project.id"
          @open="openEvent(event.id)"
        />
      </ul>
    </section>
    <p v-if="!upcoming.length" class="py-6 text-sm text-muted">Rien de prévu.</p>

    <div v-if="past.length" class="mt-2">
      <button
        type="button"
        class="text-sm font-medium text-muted hover:text-fg"
        :aria-expanded="showPast"
        @click="showPast = !showPast"
      >
        {{ showPast ? 'Masquer' : 'Afficher' }} les {{ past.length }} RDV passé{{
          past.length > 1 ? 's' : ''
        }}
      </button>
      <ul v-if="showPast" class="mt-2 border-t border-line">
        <EventRow
          v-for="event in past"
          :key="event.id"
          :event="event"
          :show-project="includeChildren && event.project !== project.id"
          @open="openEvent(event.id)"
        />
      </ul>
    </div>
  </template>

  <EventPanel
    v-model:open="eventPanelOpen"
    :event-id="eventId"
    :create-in="creating ? project.id : null"
    @changed="load"
    @created="((creating = false), openEvent($event.id))"
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
