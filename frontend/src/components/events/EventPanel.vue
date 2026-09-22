<script setup lang="ts">
/**
 * The event / meeting panel: create one (`createIn` = project id) or open
 * one (`eventId`). Three separate texts (SPECIFICATIONS §4): preparation
 * notes, the report written afterwards, and the ordered list of decisions.
 *
 * Editors change everything; everyone else reads. "Créer une tâche depuis
 * ce RDV" opens the task panel pre-filled, and the task keeps the link.
 */
import { CircleCheckBig, MapPin, Plus, Repeat, Trash2 } from 'lucide-vue-next'
import { computed, reactive, ref, watch } from 'vue'

import type { PublicUser } from '@/api/auth'
import { ApiError } from '@/api/client'
import { type Event, type EventPayload, eventsApi, type EventType } from '@/api/events'
import { membersApi } from '@/api/projects'
import type { RecurrenceScope } from '@/api/tasks'
import TagPicker from '@/components/projects/TagPicker.vue'
import MarkdownView from '@/components/tasks/MarkdownView.vue'
import RecurrenceEditor from '@/components/tasks/RecurrenceEditor.vue'
import RecurrenceScopeDialog from '@/components/tasks/RecurrenceScopeDialog.vue'
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
import { useProjectsStore } from '@/stores/projects'
import { useUiStore } from '@/stores/ui'
import { EVENT_TYPE_LABELS, EVENT_TYPE_ORDER, isPast } from '@/utils/events'
import { atLeast } from '@/utils/roles'
import {
  buildRrule,
  describeRrule,
  fromIso,
  NO_RECURRENCE,
  parseRrule,
  type RecurrenceChoice,
  TASK_STATUS_LABELS,
  toIso,
} from '@/utils/tasks'

import ContactPicker from './ContactPicker.vue'
import DecisionsEditor from './DecisionsEditor.vue'

const props = defineProps<{
  eventId?: number | null
  createIn?: number | null
  /** Creation from a calendar: the day that was clicked (YYYY-MM-DD). */
  createStart?: string | null
}>()
const emit = defineEmits<{
  changed: []
  created: [event: Event]
  /** "Créer une tâche depuis ce RDV": the host opens its task panel. */
  createTask: [event: Event]
  openTask: [id: number]
}>()
const open = defineModel<boolean>('open', { required: true })

const projects = useProjectsStore()
const ui = useUiStore()
const { loading, error, fieldErrors, submit } = useFormSubmit()

const event = ref<Event | null>(null)
const ready = ref(false)
const members = ref<PublicUser[]>([])
const recurrence = ref<RecurrenceChoice>({ ...NO_RECURRENCE })
const scopeDialog = ref<'save' | 'delete' | null>(null)
const deleteDialog = ref(false)

const form = reactive({
  type: 'meeting' as EventType,
  title: '',
  all_day: false,
  start_date: '',
  start_time: '',
  end_date: '',
  end_time: '',
  location: '',
  prep_notes: '',
  report: '',
  decisions: [] as string[],
  participants: [] as string[],
  contacts: [] as number[],
  tags: [] as number[],
})

const projectId = computed(() => event.value?.project ?? props.createIn ?? null)
const project = computed(() => (projectId.value ? projects.byId.get(projectId.value) : undefined))
const canEdit = computed(() => atLeast(project.value?.my_role, 'editor'))
const originalRule = computed(() => event.value?.recurrence?.rrule ?? '')
const over = computed(() => !!event.value && isPast(event.value))

const typeOptions = EVENT_TYPE_ORDER.map((value) => ({ value, label: EVENT_TYPE_LABELS[value] }))

function fill(source: Event | null) {
  const allDay = source?.all_day ?? false
  const start = fromIso(source?.start ?? null, allDay)
  const end = fromIso(source?.end ?? null, allDay)
  Object.assign(form, {
    type: source?.type ?? 'meeting',
    title: source?.title ?? '',
    all_day: allDay,
    start_date: source ? start.date : (props.createStart ?? ''),
    start_time: source ? start.time : '',
    end_date: source ? end.date : (props.createStart ?? ''),
    end_time: source ? end.time : '',
    location: source?.location ?? '',
    prep_notes: source?.prep_notes ?? '',
    report: source?.report ?? '',
    decisions: [...(source?.decisions ?? [])],
    participants: source?.participants.map((user) => user.username) ?? [],
    contacts: [...(source?.contacts ?? [])],
    tags: [...(source?.tags ?? [])],
  })
  recurrence.value = parseRrule(source?.recurrence?.rrule)
}

async function load() {
  ready.value = false
  error.value = ''
  fieldErrors.value = {}
  event.value = null
  try {
    if (props.eventId) event.value = await eventsApi.get(props.eventId)
    fill(event.value)
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
        ? "Ce RDV n'existe plus, ou tu n'y as pas accès."
        : 'Le RDV ne peut pas être ouvert.',
      'error',
    )
  }
}

watch(
  () => [open.value, props.eventId, props.createIn] as const,
  ([isOpen]) => isOpen && load(),
  { immediate: true },
)

// A new event lasts one hour (SPECIFICATIONS §4): the end follows the start
// until the user sets it by hand.
watch(
  () => [form.start_date, form.start_time],
  ([date, time], [oldDate, oldTime]) => {
    if (event.value) return
    if (form.end_date === oldDate || !form.end_date) form.end_date = date
    if (!form.all_day && (form.end_time === oldTime || !form.end_time) && time) {
      const [h, m] = time.split(':').map(Number)
      form.end_time = `${String((h + 1) % 24).padStart(2, '0')}:${String(m).padStart(2, '0')}`
    }
  },
)

function toggleParticipant(username: string) {
  form.participants = form.participants.includes(username)
    ? form.participants.filter((name) => name !== username)
    : [...form.participants, username]
}

function payload(): EventPayload {
  const rule = buildRrule(recurrence.value)
  return {
    type: form.type,
    title: form.title.trim(),
    all_day: form.all_day,
    start: toIso(form.start_date, form.start_time, form.all_day) ?? undefined,
    end: toIso(form.end_date || form.start_date, form.end_time, form.all_day) ?? undefined,
    location: form.location.trim(),
    prep_notes: form.prep_notes,
    report: form.report,
    decisions: form.decisions,
    participant_usernames: form.participants,
    contacts: form.contacts,
    tags: form.tags,
    // Only sent when it changed: "" means "stop recurring from here".
    ...(rule !== originalRule.value ? { rrule: rule } : {}),
  }
}

const ruleChanged = computed(() => buildRrule(recurrence.value) !== originalRule.value)

function onSave() {
  if (event.value?.recurrence) scopeDialog.value = 'save'
  else save('this')
}

async function save(scope: RecurrenceScope) {
  scopeDialog.value = null
  let saved: Event | undefined
  const ok = await submit(async () => {
    saved = event.value
      ? await eventsApi.update(event.value.id, payload(), scope)
      : await eventsApi.create({
          ...payload(),
          project: props.createIn!,
          title: form.title.trim(),
          start: toIso(form.start_date, form.start_time, form.all_day)!,
        })
  })
  if (!ok || !saved) return
  const created = !event.value
  event.value = saved
  fill(saved)
  ui.toast(created ? 'RDV créé' : 'RDV enregistré', 'success')
  emit('changed')
  if (created) emit('created', saved)
}

function onDelete() {
  if (event.value?.recurrence) scopeDialog.value = 'delete'
  else deleteDialog.value = true
}

async function remove(scope: RecurrenceScope) {
  scopeDialog.value = null
  deleteDialog.value = false
  if (!event.value) return
  try {
    await eventsApi.remove(event.value.id, scope)
    ui.toast('RDV supprimé', 'success')
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
    :title="event ? EVENT_TYPE_LABELS[event.type] : 'Nouveau RDV'"
    :description="project?.name"
  >
    <div v-if="!ready" class="space-y-4">
      <SkeletonBlock class="h-10 w-full" />
      <SkeletonBlock class="h-24 w-full" />
      <SkeletonBlock class="h-40 w-full" />
    </div>

    <form v-else id="event-form" class="space-y-5" @submit.prevent="onSave">
      <FormError :message="error || fieldErrors.rrule?.[0] || fieldErrors.contacts?.[0]" />

      <BaseInput
        v-model="form.title"
        label="Titre"
        required
        :disabled="!canEdit"
        :errors="fieldErrors.title"
      />
      <div class="grid grid-cols-2 gap-4">
        <BaseSelect v-model="form.type" label="Type" :options="typeOptions" :disabled="!canEdit" />
        <BaseInput
          v-model="form.location"
          label="Lieu"
          placeholder="Studio, Zoom…"
          :disabled="!canEdit"
        />
      </div>

      <fieldset :disabled="!canEdit" class="space-y-3">
        <BaseSwitch v-model="form.all_day" label="Journée entière" :disabled="!canEdit" />
        <div class="grid grid-cols-2 gap-x-4 gap-y-3">
          <BaseInput
            v-model="form.start_date"
            label="Début"
            type="date"
            required
            :errors="fieldErrors.start"
          />
          <BaseInput v-model="form.end_date" label="Fin" type="date" :errors="fieldErrors.end" />
          <template v-if="!form.all_day">
            <BaseInput v-model="form.start_time" label="Heure de début" type="time" />
            <BaseInput v-model="form.end_time" label="Heure de fin" type="time" />
          </template>
        </div>
      </fieldset>

      <div>
        <p class="mb-1.5 text-sm font-medium">Participants (membres du projet)</p>
        <div class="flex flex-wrap gap-1.5">
          <button
            v-for="user in members"
            :key="user.username"
            type="button"
            :disabled="!canEdit"
            :aria-pressed="form.participants.includes(user.username)"
            class="inline-flex h-8 items-center gap-1.5 rounded-full border pr-3 pl-1 text-sm transition-colors disabled:cursor-default"
            :class="
              form.participants.includes(user.username)
                ? 'border-fg bg-surface-2 font-medium'
                : 'border-line text-muted enabled:hover:text-fg'
            "
            @click="toggleParticipant(user.username)"
          >
            <AppAvatar :name="user.display_name" :src="user.avatar_url" :size="22" />
            {{ user.display_name }}
          </button>
        </div>
        <p v-if="fieldErrors.participant_usernames" class="mt-1.5 text-sm text-danger">
          {{ fieldErrors.participant_usernames[0] }}
        </p>
      </div>

      <ContactPicker
        v-if="project"
        v-model="form.contacts"
        :workspace-id="project.workspace"
        :current="event?.contact_details ?? []"
        :disabled="!canEdit"
      />

      <TagPicker v-if="project && canEdit" v-model="form.tags" :workspace-id="project.workspace" />

      <div>
        <p class="mb-1.5 flex items-center gap-2 text-sm font-medium">
          <Repeat class="size-4" aria-hidden="true" /> Récurrence
        </p>
        <RecurrenceEditor v-if="canEdit" v-model="recurrence" />
        <p v-else class="text-sm text-muted">{{ describeRrule(originalRule) || 'Aucune' }}</p>
      </div>

      <!-- Before: preparation. After: minutes and decisions. -->
      <BaseTextarea
        v-if="canEdit"
        v-model="form.prep_notes"
        label="Notes de préparation (markdown simple)"
        :rows="3"
      />
      <div v-else-if="form.prep_notes">
        <p class="mb-1.5 text-sm font-medium">Notes de préparation</p>
        <MarkdownView :source="form.prep_notes" />
      </div>

      <template v-if="event">
        <BaseTextarea
          v-if="canEdit"
          v-model="form.report"
          label="Compte rendu (après le RDV)"
          :rows="4"
        />
        <div v-else-if="form.report">
          <p class="mb-1.5 text-sm font-medium">Compte rendu</p>
          <MarkdownView :source="form.report" />
        </div>
        <DecisionsEditor v-model="form.decisions" :disabled="!canEdit" />
      </template>
      <p v-else class="text-sm text-muted">
        Le compte rendu et les décisions se notent une fois le RDV créé.
      </p>
    </form>

    <!-- Tasks born from this meeting (SPEC §8). -->
    <section v-if="ready && event" class="mt-7">
      <h3 class="mb-2 flex items-center justify-between text-sm font-semibold">
        Tâches issues de ce RDV
        <BaseButton v-if="canEdit" variant="secondary" @click="emit('createTask', event)">
          <Plus class="size-4" aria-hidden="true" /> Créer une tâche
        </BaseButton>
      </h3>
      <ul v-if="event.tasks.length" class="space-y-1">
        <li v-for="task in event.tasks" :key="task.id">
          <button
            type="button"
            class="flex w-full items-center gap-2 rounded-lg px-2 py-1.5 text-left text-sm hover:bg-surface-2"
            @click="emit('openTask', task.id)"
          >
            <CircleCheckBig class="size-4 shrink-0 text-muted" aria-hidden="true" />
            <span
              class="min-w-0 flex-1 truncate"
              :class="task.status === 'done' ? 'text-muted line-through' : ''"
            >
              {{ task.title }}
            </span>
            <span class="text-xs text-muted">{{ TASK_STATUS_LABELS[task.status] }}</span>
          </button>
        </li>
      </ul>
      <p v-else class="text-sm text-muted">Aucune pour l'instant.</p>
    </section>

    <p v-if="ready && event?.location" class="mt-4 flex items-center gap-1.5 text-sm text-muted">
      <MapPin class="size-4" aria-hidden="true" /> {{ event.location }}
      <span v-if="over">· terminé</span>
    </p>

    <template v-if="ready && canEdit" #footer>
      <button
        v-if="event"
        type="button"
        class="mr-auto rounded-lg p-2 text-muted hover:bg-surface-2 hover:text-danger"
        aria-label="Supprimer le RDV"
        @click="onDelete"
      >
        <Trash2 class="size-4" aria-hidden="true" />
      </button>
      <BaseButton variant="secondary" @click="open = false">Fermer</BaseButton>
      <BaseButton type="submit" form="event-form" :loading="loading">
        {{ event ? 'Enregistrer' : 'Créer' }}
      </BaseButton>
    </template>
  </SidePanel>

  <RecurrenceScopeDialog
    :open="scopeDialog !== null"
    :action="scopeDialog ?? 'save'"
    :following-only="scopeDialog === 'save' && ruleChanged"
    noun="RDV récurrent"
    @update:open="(value: boolean) => !value && (scopeDialog = null)"
    @choose="onScopeChosen"
  />
  <ConfirmDialog
    v-model:open="deleteDialog"
    title="Supprimer ce RDV ?"
    confirm-label="Supprimer"
    danger
    @confirm="remove('this')"
  >
    <p>Ses notes, son compte rendu et ses décisions seront supprimés aussi.</p>
  </ConfirmDialog>
</template>
