<script setup lang="ts">
/**
 * Overview of a project = its mini-dashboard (SPEC §15, page 3): what is late,
 * what is for today, the next milestones, then the sub-projects sorted into
 * Passé / En cours / À venir, and the budget for those who may see money.
 * Everything covers the project AND its sub-projects.
 */
import { CalendarClock, CircleCheckBig, Flag, FlagOff } from 'lucide-vue-next'
import { computed, ref, watch } from 'vue'
import { RouterLink } from 'vue-router'

import { ApiError } from '@/api/client'
import { dashboardApi, type Milestone, type ProjectOverview } from '@/api/dashboard'
import type { Project, Temporal } from '@/api/projects'
import { type Task, tasksApi } from '@/api/tasks'
import StatusBadge from '@/components/projects/StatusBadge.vue'
import EventPanel from '@/components/events/EventPanel.vue'
import TaskPanel from '@/components/tasks/TaskPanel.vue'
import TaskRow from '@/components/tasks/TaskRow.vue'
import ColorDot from '@/components/ui/ColorDot.vue'
import SkeletonBlock from '@/components/ui/SkeletonBlock.vue'
import { useEventPanel } from '@/composables/useEventPanel'
import { useTaskPanel } from '@/composables/useTaskPanel'
import { useAuthStore } from '@/stores/auth'
import { useProjectsStore } from '@/stores/projects'
import { useUiStore } from '@/stores/ui'
import { chf, percentOf } from '@/utils/money'
import { formatDate, formatDateRange, TEMPORAL_LABELS } from '@/utils/projects'
import { atLeast } from '@/utils/roles'

const props = defineProps<{ project: Project }>()
const projects = useProjectsStore()
const auth = useAuthStore()
const ui = useUiStore()
const { taskId, openTask, closeTask } = useTaskPanel()
const { eventId, openEvent, closeEvent } = useEventPanel()

const overview = ref<ProjectOverview | null>(null)

async function load() {
  overview.value = await dashboardApi.projectOverview(props.project.id)
}
watch(() => props.project.id, load, { immediate: true })

const COLUMNS: Temporal[] = ['past', 'current', 'upcoming']
const children = computed(() => projects.childrenOf(props.project.id))
const byTemporal = computed(() =>
  Object.fromEntries(
    COLUMNS.map((key) => [key, children.value.filter((child) => child.temporal === key)]),
  ),
)

const MILESTONE_ICONS = {
  task: CircleCheckBig,
  event: CalendarClock,
  project_start: Flag,
  project_end: FlagOff,
}
const MILESTONE_LABELS = {
  task: 'Échéance',
  event: 'RDV',
  project_start: 'Début',
  project_end: 'Fin',
}
// Tasks and events open their panel; project dates lead to the project.
const opensPanel = (kind: Milestone['kind']) => kind === 'task' || kind === 'event'

function openMilestone(milestone: Milestone) {
  if (milestone.kind === 'task') openTask(milestone.id)
  else if (milestone.kind === 'event') openEvent(milestone.id)
}

function canComplete(task: Task): boolean {
  const role = projects.byId.get(task.project)?.my_role
  if (atLeast(role, 'editor')) return true
  const mine = task.assignees.some((user) => user.username === auth.user?.username)
  return mine && atLeast(role, 'commenter')
}

async function toggleDone(task: Task) {
  try {
    await tasksApi.update(task.id, { status: task.status === 'done' ? 'todo' : 'done' })
    await load()
  } catch (error) {
    ui.toast(error instanceof ApiError ? error.message : 'Le statut est resté inchangé.', 'error')
  }
}

const panelOpen = computed({
  get: () => taskId.value !== null,
  set: (value) => !value && closeTask(),
})
const eventPanelOpen = computed({
  get: () => eventId.value !== null,
  set: (value) => !value && closeEvent(),
})
</script>

<template>
  <div class="space-y-8">
    <section v-if="project.description">
      <h2 class="mb-2 text-sm font-semibold text-muted">Description</h2>
      <p class="max-w-3xl whitespace-pre-line">{{ project.description }}</p>
    </section>

    <div v-if="!overview" class="grid gap-4 lg:grid-cols-3">
      <SkeletonBlock v-for="n in 3" :key="n" class="h-40" />
    </div>

    <div v-else class="grid gap-4 lg:grid-cols-3">
      <section
        class="rounded-2xl border p-4"
        :class="overview.overdue.count ? 'border-danger' : 'border-line'"
      >
        <h2
          class="mb-1 flex items-center justify-between text-sm font-semibold"
          :class="overview.overdue.count ? 'text-danger' : ''"
        >
          En retard <span class="font-normal text-muted">{{ overview.overdue.count }}</span>
        </h2>
        <ul v-if="overview.overdue.count">
          <TaskRow
            v-for="task in overview.overdue.items"
            :key="task.id"
            :task="task"
            :show-project="task.project !== project.id"
            :can-complete="canComplete(task)"
            @open="openTask(task.id)"
            @toggle-done="toggleDone(task)"
          />
        </ul>
        <p v-else class="py-4 text-sm text-muted">Rien en retard.</p>
      </section>

      <section class="rounded-2xl border border-line p-4">
        <h2 class="mb-1 flex items-center justify-between text-sm font-semibold">
          Aujourd'hui <span class="font-normal text-muted">{{ overview.today.count }}</span>
        </h2>
        <ul v-if="overview.today.count">
          <TaskRow
            v-for="task in overview.today.items"
            :key="task.id"
            :task="task"
            :show-project="task.project !== project.id"
            :can-complete="canComplete(task)"
            @open="openTask(task.id)"
            @toggle-done="toggleDone(task)"
          />
        </ul>
        <p v-else class="py-4 text-sm text-muted">Rien de prévu aujourd'hui.</p>
      </section>

      <section class="rounded-2xl border border-line p-4">
        <h2 class="mb-2 text-sm font-semibold">Prochains jalons</h2>
        <ul v-if="overview.milestones.length" class="space-y-2.5">
          <li v-for="milestone in overview.milestones" :key="`${milestone.kind}-${milestone.id}`">
            <component
              :is="opensPanel(milestone.kind) ? 'button' : RouterLink"
              :type="opensPanel(milestone.kind) ? 'button' : undefined"
              :to="opensPanel(milestone.kind) ? undefined : `/projets/${milestone.project}`"
              class="flex w-full items-start gap-2.5 text-left"
              @click="openMilestone(milestone)"
            >
              <component
                :is="MILESTONE_ICONS[milestone.kind]"
                class="mt-0.5 size-4 shrink-0 text-muted"
                aria-hidden="true"
              />
              <span class="min-w-0 flex-1">
                <span class="block truncate text-sm font-medium hover:underline">
                  {{ milestone.title }}
                </span>
                <span class="flex items-center gap-1.5 text-xs text-muted">
                  <ColorDot :color="milestone.color" />
                  {{ MILESTONE_LABELS[milestone.kind] }} · {{ formatDate(milestone.date) }}
                </span>
              </span>
            </component>
          </li>
        </ul>
        <p v-else class="py-2 text-sm text-muted">Aucune date à venir.</p>
      </section>
    </div>

    <!-- Budget: only with can_view_finance (the API answers null otherwise). -->
    <section v-if="overview?.budget" class="rounded-2xl border border-line p-4">
      <h2 class="mb-3 flex items-center justify-between text-sm font-semibold">
        Budget
        <RouterLink
          :to="`/projets/${project.id}/compta`"
          class="text-xs font-medium text-muted hover:text-fg"
        >
          Voir la compta
        </RouterLink>
      </h2>
      <div class="grid gap-4 sm:grid-cols-2">
        <div v-for="scope in ['own', 'with_children'] as const" :key="scope">
          <p class="text-xs font-medium text-muted">
            {{ scope === 'own' ? 'Ce projet' : 'Avec les sous-projets' }}
          </p>
          <p class="mt-1 text-sm">
            Dépenses
            <strong class="tabular-nums">{{ chf(overview.budget[scope].actual_expense) }}</strong>
            <span class="text-muted"
              >/ {{ chf(overview.budget[scope].planned_expense) }} prévus</span
            >
          </p>
          <div class="mt-1.5 h-1.5 overflow-hidden rounded-full bg-surface-2" aria-hidden="true">
            <div
              class="h-full rounded-full"
              :class="
                Number(overview.budget[scope].actual_expense) >
                Number(overview.budget[scope].planned_expense)
                  ? 'bg-danger'
                  : 'bg-accent'
              "
              :style="{
                width: `${percentOf(overview.budget[scope].actual_expense, overview.budget[scope].planned_expense)}%`,
              }"
            />
          </div>
          <p class="mt-1 text-sm text-muted">
            Recettes
            <span class="tabular-nums">{{ chf(overview.budget[scope].actual_income) }}</span> /
            {{ chf(overview.budget[scope].planned_income) }} prévues
          </p>
        </div>
      </div>
      <p
        v-if="overview.budget.needs_receipt || Number(overview.budget.to_pay) > 0"
        class="mt-3 text-sm"
      >
        <span v-if="overview.budget.needs_receipt" class="font-semibold text-danger">
          {{ overview.budget.needs_receipt }} dépense{{
            overview.budget.needs_receipt > 1 ? 's' : ''
          }}
          à justifier
        </span>
        <span v-if="overview.budget.needs_receipt && Number(overview.budget.to_pay) > 0"> · </span>
        <span v-if="Number(overview.budget.to_pay) > 0" class="font-semibold text-warning">
          {{ chf(overview.budget.to_pay) }} à payer
        </span>
      </p>
    </section>

    <section>
      <h2 class="mb-3 text-sm font-semibold text-muted">Sous-projets</h2>
      <p v-if="!children.length" class="text-sm text-muted">Aucun sous-projet pour l'instant.</p>
      <div v-else class="grid gap-4 md:grid-cols-3">
        <div v-for="key in COLUMNS" :key="key" class="rounded-2xl border border-line p-3">
          <h3 class="mb-2 px-1 text-sm font-semibold">
            {{ TEMPORAL_LABELS[key] }}
            <span class="font-normal text-muted">{{ byTemporal[key].length }}</span>
          </h3>
          <ul class="space-y-2">
            <li v-for="child in byTemporal[key]" :key="child.id">
              <RouterLink
                :to="`/projets/${child.id}`"
                class="block rounded-xl border border-line bg-surface p-3 hover:bg-surface-2"
              >
                <span class="flex items-center gap-2 font-medium">
                  <ColorDot :color="child.color" /> <span class="truncate">{{ child.name }}</span>
                </span>
                <span class="mt-2 flex flex-wrap items-center gap-2 text-xs text-muted">
                  <StatusBadge
                    v-if="child.status"
                    :status="child.status"
                    :overdue="child.end_overdue"
                  />
                  {{ formatDateRange(child.start_date, child.end_date) }}
                </span>
              </RouterLink>
            </li>
            <li v-if="!byTemporal[key].length" class="px-1 py-2 text-sm text-muted">—</li>
          </ul>
        </div>
      </div>
    </section>
  </div>

  <TaskPanel v-model:open="panelOpen" :task-id="taskId" @changed="load" @open-event="openEvent" />
  <EventPanel
    v-model:open="eventPanelOpen"
    :event-id="eventId"
    @changed="load"
    @open-task="openTask"
  />
</template>
