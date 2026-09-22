<script setup lang="ts">
/**
 * Tasks on a calendar (FullCalendar): month, week, day and agenda.
 * Used by the "Calendrier" view of a project and by the global calendar page;
 * events and external calendars join the same component in phases 6 and 11.
 *
 * The parent owns the data: this component tells it which period is on screen
 * (`range`), and reports what the user did (`open`, `create`, `changed`).
 * Dragging or stretching an event changes the task dates (editors only);
 * on a recurring task that means "this occurrence".
 *
 * Titles are rendered by FullCalendar as text, never as HTML.
 */
import type { CalendarOptions, DatesSetArg, EventClickArg, EventDropArg } from '@fullcalendar/core'
import frLocale from '@fullcalendar/core/locales/fr'
import dayGridPlugin from '@fullcalendar/daygrid'
import interactionPlugin, {
  type DateClickArg,
  type EventResizeDoneArg,
} from '@fullcalendar/interaction'
import listPlugin from '@fullcalendar/list'
import timeGridPlugin from '@fullcalendar/timegrid'
import FullCalendar from '@fullcalendar/vue3'
import { computed } from 'vue'

import { ApiError } from '@/api/client'
import { type Task, tasksApi } from '@/api/tasks'
import { useUiStore } from '@/stores/ui'
import { calendarEvents, datesAfterCalendarChange } from '@/utils/taskViews'

const props = defineProps<{
  tasks: Task[]
  canMove: (task: Task) => boolean
  /** Clicking an empty day proposes a new task due that day. */
  canCreate?: boolean
}>()
const emit = defineEmits<{
  open: [task: Task]
  create: [dateKey: string]
  changed: []
  range: [start: Date, end: Date]
}>()

const ui = useUiStore()

// A month grid is unreadable at 375 px: phones start on the agenda.
const narrow = window.matchMedia('(max-width: 639px)').matches

async function onMoved(info: EventDropArg | EventResizeDoneArg) {
  const task = info.event.extendedProps.task as Task
  const dates = datesAfterCalendarChange(task, {
    allDay: info.event.allDay,
    start: info.event.start!,
    end: info.event.end,
  })
  try {
    await tasksApi.update(task.id, dates)
    emit('changed')
  } catch (error) {
    info.revert()
    ui.toast(error instanceof ApiError ? error.message : "La date n'a pas été changée.", 'error')
  }
}

// Built once: only `events` changes afterwards, so FullCalendar never resets
// its handlers or its view when the tasks are reloaded.
const base: CalendarOptions = {
  plugins: [dayGridPlugin, timeGridPlugin, listPlugin, interactionPlugin],
  locale: frLocale,
  firstDay: 1,
  initialView: narrow ? 'listWeek' : 'dayGridMonth',
  headerToolbar: {
    left: 'prev,next today',
    center: 'title',
    right: 'dayGridMonth,timeGridWeek,timeGridDay,listWeek',
  },
  buttonText: { listWeek: 'Agenda' },
  height: 'auto',
  dayMaxEvents: 4,
  // Every task is a block in its project colour (timed ones would be dots).
  eventDisplay: 'block',
  nowIndicator: true,
  scrollTime: '08:00:00',
  eventTimeFormat: { hour: '2-digit', minute: '2-digit', hour12: false },
  slotLabelFormat: { hour: '2-digit', minute: '2-digit', hour12: false },
  // Each event says whether it may move (`editable`), from the user's rights.
  editable: true,
  eventDurationEditable: true,
  longPressDelay: 400,
  eventClick: (info: EventClickArg) => emit('open', info.event.extendedProps.task as Task),
  eventDrop: onMoved,
  eventResize: onMoved,
  dateClick: (info: DateClickArg) => {
    if (props.canCreate) emit('create', info.dateStr.slice(0, 10))
  },
  datesSet: (info: DatesSetArg) => emit('range', info.start, info.end),
}

const options = computed<CalendarOptions>(() => ({
  ...base,
  events: calendarEvents(props.tasks, props.canMove),
}))
</script>

<template>
  <div class="task-calendar" :class="canCreate ? 'task-calendar-creatable' : ''">
    <FullCalendar :options="options" />
  </div>
</template>
