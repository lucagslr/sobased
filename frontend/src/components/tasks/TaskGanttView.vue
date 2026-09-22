<script setup lang="ts">
/**
 * Gantt chart of the dated tasks: the ONLY file that knows frappe-gantt
 * (docs/PLAN.md, risk 10). Bars take the project colour, arrows follow
 * "Bloquée par" (SPEC §7: arrows, nothing more), day precision.
 *
 * Security: frappe-gantt writes task names with innerHTML, in the bar label
 * and in its popup. Names are therefore escaped (utils/taskViews.ganttRows)
 * and the popup is disabled: a click opens our own task panel instead.
 *
 * Limits: the library listens to the mouse only, so bars cannot be dragged
 * with a finger (dates are then changed in the panel), and "read only" is
 * global: a drag the server refuses is simply rolled back.
 */
import 'frappe-gantt/dist/frappe-gantt.css'

import Gantt, { type GanttTask, type GanttViewMode } from 'frappe-gantt'
import { GanttChartSquare } from 'lucide-vue-next'
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'

import { ApiError } from '@/api/client'
import { type Task, tasksApi } from '@/api/tasks'
import EmptyState from '@/components/ui/EmptyState.vue'
import SegmentedControl from '@/components/ui/SegmentedControl.vue'
import { useUiStore } from '@/stores/ui'
import { localDateKey } from '@/utils/tasks'
import { datesAfterGanttChange, ganttRows } from '@/utils/taskViews'

const props = defineProps<{ tasks: Task[]; canMove: (task: Task) => boolean }>()
const emit = defineEmits<{ open: [task: Task]; changed: [] }>()

const ui = useUiStore()
const container = ref<HTMLElement | null>(null)
const mode = ref<GanttViewMode>('Week')
let chart: Gantt | null = null

const MODES: { value: GanttViewMode; label: string }[] = [
  { value: 'Day', label: 'Jour' },
  { value: 'Week', label: 'Semaine' },
  { value: 'Month', label: 'Mois' },
]

const data = computed(() => ganttRows(props.tasks))
const byId = computed(() => new Map(props.tasks.map((task) => [String(task.id), task])))
const readonly = computed(() => !props.tasks.some(props.canMove))

async function onDateChange(row: GanttTask, start: Date, end: Date) {
  const task = byId.value.get(row.id)
  if (!task) return
  const dates = datesAfterGanttChange(task, localDateKey(start), localDateKey(end))
  try {
    await tasksApi.update(task.id, dates)
  } catch (error) {
    ui.toast(error instanceof ApiError ? error.message : "La date n'a pas été changée.", 'error')
  }
  emit('changed') // also redraws the bar where the server says it is
}

function draw() {
  if (!container.value || !data.value.rows.length) {
    chart = null // the host element is gone (empty state): start over next time
    return
  }
  if (chart) {
    // New rows, then one redraw that keeps the scroll position and the scale
    // (refresh() alone would jump back to today in the initial scale).
    chart.setup_tasks(data.value.rows)
    chart.update_options({ readonly: readonly.value, view_mode: mode.value })
    return
  }
  chart = new Gantt(container.value, data.value.rows, {
    view_mode: mode.value,
    language: 'fr',
    popup: false,
    readonly: readonly.value,
    readonly_progress: true, // progress comes from the checklist
    move_dependencies: false, // moving a task never moves the ones it blocks
    today_button: false,
    view_mode_select: false,
    infinite_padding: false,
    scroll_to: 'today',
    bar_height: 26,
    padding: 16,
    container_height: 'auto',
    on_click: (row) => {
      const task = byId.value.get(row.id)
      if (task) emit('open', task)
    },
    on_date_change: onDateChange,
  })
}

onMounted(draw)
// "post": the host <div> must exist again when rows come back after an empty state.
watch(data, draw, { flush: 'post' })
watch(mode, (value) => chart?.change_view_mode(value, true))
onBeforeUnmount(() => {
  chart = null
  if (container.value) container.value.innerHTML = ''
})
</script>

<template>
  <EmptyState
    v-if="!data.rows.length"
    :icon="GanttChartSquare"
    title="Aucune tâche datée"
    text="Le Gantt montre les tâches qui ont une date de début ou une échéance. Ajoute une date à une tâche pour la voir ici."
  />
  <div v-else>
    <div class="mb-3 flex flex-wrap items-center justify-between gap-3">
      <SegmentedControl v-model="mode" label="Échelle du Gantt" :options="MODES" />
      <p v-if="data.undated.length" class="text-sm text-muted">
        {{ data.undated.length }} tâche{{ data.undated.length > 1 ? 's' : '' }} sans date
        {{ data.undated.length > 1 ? 'ne sont pas affichées' : "n'est pas affichée" }}.
      </p>
    </div>
    <div class="task-gantt overflow-hidden rounded-2xl border border-line">
      <div ref="container" />
    </div>
    <p class="mt-2 text-xs text-muted sm:hidden">
      Sur téléphone, le Gantt se consulte : touche une barre pour ouvrir la tâche et changer ses
      dates.
    </p>
  </div>
</template>
