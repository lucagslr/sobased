<script setup lang="ts">
/**
 * The task panel: create a task (`createIn` = project id) or open one
 * (`taskId`). Main fields are saved with the button; checklist and comments
 * save themselves at once through their own endpoints.
 *
 * What is editable follows the rights (SPECIFICATIONS §1.3):
 * - editor and up: everything;
 * - the assignee with the Commenter role: the status and ticking the checklist;
 * - commenter: comments; viewer: nothing.
 */
import { CalendarClock, Repeat, Trash2 } from 'lucide-vue-next'
import { computed, reactive, ref, watch } from 'vue'

import type { PublicUser } from '@/api/auth'
import { ApiError } from '@/api/client'
import { membersApi } from '@/api/projects'
import {
  type Blocker,
  type ChecklistItem,
  type RecurrenceScope,
  type Task,
  type TaskPayload,
  tasksApi,
  type TaskStatus,
} from '@/api/tasks'
import TagPicker from '@/components/projects/TagPicker.vue'
import AppAvatar from '@/components/ui/AppAvatar.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import BaseInput from '@/components/ui/BaseInput.vue'
import BaseSelect from '@/components/ui/BaseSelect.vue'
import BaseSwitch from '@/components/ui/BaseSwitch.vue'
import BaseTextarea from '@/components/ui/BaseTextarea.vue'
import ConfirmDialog from '@/components/ui/ConfirmDialog.vue'
import FormError from '@/components/ui/FormError.vue'
import SidePanel from '@/components/ui/SidePanel.vue'
import SkeletonBlock from '@/components/ui/SkeletonBlock.vue'
import { useFormSubmit } from '@/composables/useFormSubmit'
import { useAuthStore } from '@/stores/auth'
import { useProjectsStore } from '@/stores/projects'
import { useUiStore } from '@/stores/ui'
import { atLeast } from '@/utils/roles'
import {
  buildRrule,
  describeRrule,
  formatTaskDate,
  fromIso,
  NO_RECURRENCE,
  parseRrule,
  PRIORITIES,
  type RecurrenceChoice,
  TASK_STATUS_LABELS,
  TASK_STATUS_ORDER,
  toIso,
} from '@/utils/tasks'

import BlockedByField from './BlockedByField.vue'
import MarkdownView from './MarkdownView.vue'
import RecurrenceEditor from './RecurrenceEditor.vue'
import RecurrenceScopeDialog from './RecurrenceScopeDialog.vue'
import TaskChecklist from './TaskChecklist.vue'
import TaskComments from './TaskComments.vue'

const props = defineProps<{
  taskId?: number | null
  createIn?: number | null
  /** Creation from a calendar: the day that was clicked (YYYY-MM-DD). */
  createDue?: string | null
  /** "Créer une tâche depuis ce RDV": the meeting the new task comes from. */
  createFromEvent?: { id: number; title: string } | null
}>()
const emit = defineEmits<{ changed: []; created: [task: Task]; openEvent: [id: number] }>()
const open = defineModel<boolean>('open', { required: true })

const auth = useAuthStore()
const projects = useProjectsStore()
const ui = useUiStore()
const { loading, error, fieldErrors, submit } = useFormSubmit()

const task = ref<Task | null>(null)
const ready = ref(false)
const members = ref<PublicUser[]>([])
const checklist = ref<ChecklistItem[]>([])
const blockers = ref<Blocker[]>([])
const recurrence = ref<RecurrenceChoice>({ ...NO_RECURRENCE })
const scopeDialog = ref<'save' | 'delete' | null>(null)
const deleteDialog = ref(false)

const form = reactive({
  title: '',
  description: '',
  status: 'todo' as TaskStatus,
  priority: '3',
  all_day: true,
  start_date: '',
  start_time: '',
  due_date: '',
  due_time: '',
  assignees: [] as string[],
  tags: [] as number[],
})

const projectId = computed(() => task.value?.project ?? props.createIn ?? null)
const project = computed(() => (projectId.value ? projects.byId.get(projectId.value) : undefined))
const role = computed(() => project.value?.my_role ?? null)
const canEdit = computed(() => atLeast(role.value, 'editor'))
const canComment = computed(() => atLeast(role.value, 'commenter'))
const isAssignee = computed(
  () => !!task.value?.assignees.some((user) => user.username === auth.user?.username),
)
// Decision D6: the assignee may move their own task forward.
const canChangeStatus = computed(() => canEdit.value || (isAssignee.value && canComment.value))
const originalRule = computed(() => task.value?.recurrence?.rrule ?? '')

const statusOptions = TASK_STATUS_ORDER.map((value) => ({
  value,
  label: TASK_STATUS_LABELS[value],
}))
const priorityOptions = [5, 4, 3, 2, 1].map((level) => ({
  value: String(level),
  label: `${level} · ${PRIORITIES[level].label}`,
}))

function fill(source: Task | null) {
  const start = fromIso(source?.start_at ?? null, source?.all_day ?? true)
  const due = fromIso(source?.due_at ?? null, source?.all_day ?? true)
  Object.assign(form, {
    title: source?.title ?? '',
    description: source?.description ?? '',
    status: source?.status ?? 'todo',
    priority: String(source?.priority ?? 3),
    all_day: source?.all_day ?? true,
    start_date: start.date,
    start_time: start.time,
    due_date: source ? due.date : (props.createDue ?? ''),
    due_time: due.time,
    assignees: source?.assignees.map((user) => user.username) ?? [],
    tags: [...(source?.tags ?? [])],
  })
  checklist.value = source ? [...source.checklist] : []
  blockers.value = source ? [...source.blockers] : []
  recurrence.value = parseRrule(source?.recurrence?.rrule)
}

async function load() {
  ready.value = false
  error.value = ''
  fieldErrors.value = {}
  task.value = null
  try {
    if (props.taskId) task.value = await tasksApi.get(props.taskId)
    fill(task.value)
    if (!projects.loaded) await projects.load()
    if (projectId.value) {
      const effective = await membersApi.list({ project: projectId.value })
      members.value = effective.map((member) => member.user)
    }
    ready.value = true
  } catch (caught) {
    open.value = false
    ui.toast(
      caught instanceof ApiError && caught.status === 404
        ? "Cette tâche n'existe plus, ou tu n'y as pas accès."
        : 'La tâche ne peut pas être ouverte.',
      'error',
    )
  }
}

watch(
  () => [open.value, props.taskId, props.createIn] as const,
  ([isOpen]) => isOpen && load(),
  { immediate: true },
)

function toggleAssignee(username: string) {
  form.assignees = form.assignees.includes(username)
    ? form.assignees.filter((name) => name !== username)
    : [...form.assignees, username]
}

function payload(): TaskPayload {
  if (!canEdit.value) return { status: form.status } // D6: nothing else is allowed
  const rule = buildRrule(recurrence.value)
  return {
    title: form.title.trim(),
    description: form.description,
    status: form.status,
    priority: Number(form.priority),
    all_day: form.all_day,
    start_at: toIso(form.start_date, form.start_time, form.all_day),
    due_at: toIso(form.due_date, form.due_time, form.all_day),
    assignee_usernames: form.assignees,
    tags: form.tags,
    ...(task.value ? { blocked_by: blockers.value.map((blocker) => blocker.id) } : {}),
    // Only sent when it changed: "" means "stop recurring from here".
    ...(rule !== originalRule.value ? { rrule: rule } : {}),
  }
}

const ruleChanged = computed(() => buildRrule(recurrence.value) !== originalRule.value)

function onSave() {
  // One occurrence of a series: ask which occurrences the change applies to.
  if (task.value?.recurrence && canEdit.value) scopeDialog.value = 'save'
  else save('this')
}

async function save(scope: RecurrenceScope) {
  scopeDialog.value = null
  let saved: Task | undefined
  const ok = await submit(async () => {
    saved = task.value
      ? await tasksApi.update(task.value.id, payload(), scope)
      : await tasksApi.create({
          ...payload(),
          project: props.createIn!,
          title: form.title.trim(),
          ...(props.createFromEvent ? { source_event: props.createFromEvent.id } : {}),
        })
  })
  if (!ok || !saved) return
  const created = !task.value
  task.value = saved
  fill(saved)
  ui.toast(created ? 'Tâche créée' : 'Tâche enregistrée', 'success')
  emit('changed')
  if (created) emit('created', saved)
}

function onDelete() {
  if (task.value?.recurrence) scopeDialog.value = 'delete'
  else deleteDialog.value = true
}

async function remove(scope: RecurrenceScope) {
  scopeDialog.value = null
  deleteDialog.value = false
  if (!task.value) return
  try {
    await tasksApi.remove(task.value.id, scope)
    ui.toast('Tâche supprimée', 'success')
    open.value = false
    emit('changed')
  } catch (caught) {
    ui.toast(caught instanceof ApiError ? caught.message : 'La suppression a échoué.', 'error')
  }
}

function onScopeChosen(scope: RecurrenceScope) {
  if (scopeDialog.value === 'delete') remove(scope)
  else save(scope)
}
</script>

<template>
  <SidePanel
    v-model:open="open"
    :title="task ? 'Tâche' : 'Nouvelle tâche'"
    :description="project?.name"
  >
    <div v-if="!ready" class="space-y-4">
      <SkeletonBlock class="h-10 w-full" />
      <SkeletonBlock class="h-24 w-full" />
      <SkeletonBlock class="h-40 w-full" />
    </div>

    <div v-else class="space-y-7">
      <form id="task-form" class="space-y-5" @submit.prevent="onSave">
        <FormError :message="error || fieldErrors.blocked_by?.[0] || fieldErrors.rrule?.[0]" />

        <div
          v-if="task?.is_overdue"
          class="rounded-lg bg-danger-soft px-3 py-2 text-sm font-medium text-danger"
          role="status"
        >
          Urgent : l'échéance est dépassée. Termine, annule ou replanifie cette tâche.
        </div>
        <div
          v-if="task?.is_blocked && form.status === 'in_progress'"
          class="rounded-lg bg-warning-soft px-3 py-2 text-sm text-warning"
          role="status"
        >
          Cette tâche est encore bloquée par une autre. Tu peux quand même l'avancer.
        </div>

        <!-- Where the task comes from (SPEC §8): a meeting. -->
        <button
          v-if="task?.source_event_detail"
          type="button"
          class="flex w-full items-center gap-2 rounded-lg bg-surface-2 px-3 py-2 text-left text-sm hover:bg-line/60"
          @click="emit('openEvent', task.source_event_detail.id)"
        >
          <CalendarClock class="size-4 shrink-0 text-muted" aria-hidden="true" />
          <span class="min-w-0 flex-1 truncate">
            Issue du RDV du
            {{ formatTaskDate(task.source_event_detail.start, task.source_event_detail.all_day) }}
            · {{ task.source_event_detail.title }}
          </span>
        </button>
        <p
          v-else-if="!task && createFromEvent"
          class="flex items-center gap-2 rounded-lg bg-surface-2 px-3 py-2 text-sm text-muted"
        >
          <CalendarClock class="size-4 shrink-0" aria-hidden="true" />
          <span class="min-w-0 truncate">Issue du RDV « {{ createFromEvent.title }} »</span>
        </p>

        <BaseInput
          v-model="form.title"
          label="Titre"
          required
          :disabled="!canEdit"
          :errors="fieldErrors.title"
        />
        <div class="grid grid-cols-2 gap-4">
          <BaseSelect
            v-model="form.status"
            label="Statut"
            :options="statusOptions"
            :disabled="!canChangeStatus"
          />
          <BaseSelect
            v-model="form.priority"
            label="Priorité"
            :options="priorityOptions"
            :disabled="!canEdit"
          />
        </div>

        <fieldset :disabled="!canEdit" class="space-y-3">
          <BaseSwitch v-model="form.all_day" label="Journée entière" :disabled="!canEdit" />
          <div class="grid grid-cols-2 gap-x-4 gap-y-3">
            <BaseInput v-model="form.start_date" label="Début" type="date" />
            <BaseInput
              v-model="form.due_date"
              label="Échéance"
              type="date"
              :errors="fieldErrors.due_at"
            />
            <template v-if="!form.all_day">
              <BaseInput v-model="form.start_time" label="Heure de début" type="time" />
              <BaseInput v-model="form.due_time" label="Heure d'échéance" type="time" />
            </template>
          </div>
        </fieldset>

        <div>
          <p class="mb-1.5 text-sm font-medium">Assignée à</p>
          <div class="flex flex-wrap gap-1.5">
            <button
              v-for="user in members"
              :key="user.username"
              type="button"
              :disabled="!canEdit"
              :aria-pressed="form.assignees.includes(user.username)"
              class="inline-flex h-8 items-center gap-1.5 rounded-full border pr-3 pl-1 text-sm transition-colors disabled:cursor-default"
              :class="
                form.assignees.includes(user.username)
                  ? 'border-fg bg-surface-2 font-medium'
                  : 'border-line text-muted enabled:hover:text-fg'
              "
              @click="toggleAssignee(user.username)"
            >
              <AppAvatar :name="user.display_name" :src="user.avatar_url" :size="22" />
              {{ user.display_name }}
            </button>
          </div>
          <p v-if="fieldErrors.assignee_usernames" class="mt-1.5 text-sm text-danger">
            {{ fieldErrors.assignee_usernames[0] }}
          </p>
        </div>

        <TagPicker
          v-if="project && canEdit"
          v-model="form.tags"
          :workspace-id="project.workspace"
          can-create
        />

        <BlockedByField v-if="task" v-model="blockers" :task-id="task.id" :disabled="!canEdit" />

        <div>
          <p class="mb-1.5 flex items-center gap-2 text-sm font-medium">
            <Repeat class="size-4" aria-hidden="true" /> Récurrence
          </p>
          <RecurrenceEditor v-if="canEdit" v-model="recurrence" />
          <p v-else class="text-sm text-muted">{{ describeRrule(originalRule) || 'Aucune' }}</p>
        </div>

        <BaseTextarea
          v-if="canEdit"
          v-model="form.description"
          label="Description (markdown simple)"
          :rows="4"
        />
        <div v-else-if="form.description">
          <p class="mb-1.5 text-sm font-medium">Description</p>
          <MarkdownView :source="form.description" />
        </div>
      </form>

      <!-- Checklist and comments need the task to exist. -->
      <template v-if="task">
        <section>
          <h3 class="mb-2 text-sm font-semibold">Checklist</h3>
          <TaskChecklist
            v-model="checklist"
            :task-id="task.id"
            :can-edit="canEdit"
            :can-tick="canChangeStatus"
          />
        </section>
        <section>
          <h3 class="mb-3 text-sm font-semibold">Commentaires</h3>
          <TaskComments
            :key="task.id"
            :task-id="task.id"
            :members="members"
            :can-comment="canComment"
            :is-admin="atLeast(role, 'admin')"
            @count="emit('changed')"
          />
        </section>
      </template>
      <p v-else class="text-sm text-muted">
        Checklist, dépendances et commentaires seront disponibles dès que la tâche sera créée.
      </p>
    </div>

    <template v-if="ready && canChangeStatus" #footer>
      <button
        v-if="task && canEdit"
        type="button"
        class="mr-auto rounded-lg p-2 text-muted hover:bg-surface-2 hover:text-danger"
        aria-label="Supprimer la tâche"
        @click="onDelete"
      >
        <Trash2 class="size-4" aria-hidden="true" />
      </button>
      <BaseButton variant="secondary" @click="open = false">Fermer</BaseButton>
      <BaseButton type="submit" form="task-form" :loading="loading">
        {{ task ? 'Enregistrer' : 'Créer' }}
      </BaseButton>
    </template>
  </SidePanel>

  <RecurrenceScopeDialog
    :open="scopeDialog !== null"
    :action="scopeDialog ?? 'save'"
    :following-only="scopeDialog === 'save' && ruleChanged"
    @update:open="(value: boolean) => !value && (scopeDialog = null)"
    @choose="onScopeChosen"
  />
  <ConfirmDialog
    v-model:open="deleteDialog"
    title="Supprimer cette tâche ?"
    confirm-label="Supprimer"
    danger
    @confirm="remove('this')"
  >
    <p>Sa checklist et ses commentaires seront supprimés aussi.</p>
  </ConfirmDialog>
</template>
