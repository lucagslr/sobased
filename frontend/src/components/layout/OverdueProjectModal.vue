<script setup lang="ts">
/**
 * "MARCHIOLY devait se terminer le 12.10.2026" (SPEC §5).
 *
 * Shown when the app opens, for every project whose end date has passed while
 * still open, to people who may edit it. One modal at a time, the others wait
 * in line. Three answers:
 *   - Marquer terminé  -> status "done"            (answers for everybody)
 *   - Reprogrammer     -> new end date, in the future (answers for everybody)
 *   - Me rappeler demain -> hides it for ME until tomorrow
 * Closing the modal (Escape, click outside) means "remind me tomorrow".
 */
import { useDocumentVisibility } from '@vueuse/core'
import {
  DialogContent,
  DialogDescription,
  DialogOverlay,
  DialogPortal,
  DialogRoot,
  DialogTitle,
} from 'reka-ui'
import { computed, onMounted, ref, watch } from 'vue'

import { ApiError } from '@/api/client'
import { dashboardApi, type OverdueProject } from '@/api/dashboard'
import { projectsApi } from '@/api/projects'
import BaseButton from '@/components/ui/BaseButton.vue'
import BaseInput from '@/components/ui/BaseInput.vue'
import ColorDot from '@/components/ui/ColorDot.vue'
import { useProjectsStore } from '@/stores/projects'
import { useUiStore } from '@/stores/ui'
import { formatDate } from '@/utils/projects'
import { localDateKey } from '@/utils/tasks'

const projects = useProjectsStore()
const ui = useUiStore()

const queue = ref<OverdueProject[]>([])
const rescheduling = ref(false)
const newEnd = ref('')
const busy = ref(false)
const lastCheck = ref('')

const current = computed(() => queue.value[0] ?? null)
const today = () => localDateKey(new Date())
const newEndError = computed(() =>
  newEnd.value && newEnd.value <= today() ? ['Choisis une date à venir.'] : undefined,
)

async function check() {
  lastCheck.value = today()
  try {
    queue.value = await dashboardApi.overdueProjects()
  } catch {
    queue.value = [] // never block the app for this
  }
}
onMounted(check)

// A tab left open overnight: ask again when the day has changed.
const visibility = useDocumentVisibility()
watch(visibility, (state) => {
  if (state === 'visible' && lastCheck.value !== today() && !current.value) check()
})

function next() {
  queue.value = queue.value.slice(1)
  rescheduling.value = false
  newEnd.value = ''
}

async function answer(action: () => Promise<unknown>, done: string) {
  busy.value = true
  try {
    await action()
    if (done) ui.toast(done, 'success')
    next()
  } catch (error) {
    ui.toast(
      error instanceof ApiError ? error.message : "La réponse n'a pas été enregistrée.",
      'error',
    )
  } finally {
    busy.value = false
  }
}

const markDone = () =>
  answer(async () => {
    await projectsApi.update(current.value!.id, { status: 'done' })
    await projects.load()
  }, 'Projet terminé')

const reschedule = () =>
  answer(async () => {
    await projectsApi.update(current.value!.id, { end_date: newEnd.value })
    await projects.load()
  }, 'Nouvelle date enregistrée')

const snooze = () => answer(() => dashboardApi.snoozeOverdue(current.value!.id), '')

function onOpenChange(open: boolean) {
  if (!open && current.value && !busy.value) snooze()
}
</script>

<template>
  <DialogRoot :open="current !== null" @update:open="onOpenChange">
    <DialogPortal>
      <DialogOverlay class="fixed inset-0 z-[70] bg-black/40" />
      <DialogContent
        v-if="current"
        class="fixed top-1/2 left-1/2 z-[70] w-[calc(100vw-2rem)] max-w-md -translate-x-1/2 -translate-y-1/2 rounded-2xl border border-line bg-surface p-6 shadow-2xl outline-none"
      >
        <DialogTitle class="flex items-center gap-2.5 text-lg font-semibold">
          <ColorDot :color="current.color" size="md" />
          <span class="min-w-0 truncate">{{ current.name }}</span>
        </DialogTitle>
        <DialogDescription class="mt-2 text-[15px] leading-relaxed">
          <strong>{{ current.name }}</strong> devait se terminer le
          <strong>{{ formatDate(current.end_date) }}</strong
          >. C'est terminé, ou il faut reprogrammer ?
        </DialogDescription>

        <form v-if="rescheduling" class="mt-5 space-y-4" @submit.prevent="reschedule">
          <BaseInput
            v-model="newEnd"
            label="Nouvelle date de fin"
            type="date"
            required
            :errors="newEndError"
          />
          <div class="flex justify-end gap-2">
            <BaseButton variant="secondary" @click="rescheduling = false">Retour</BaseButton>
            <BaseButton type="submit" :loading="busy" :disabled="!newEnd || !!newEndError">
              Reprogrammer
            </BaseButton>
          </div>
        </form>

        <div v-else class="mt-6 space-y-2">
          <BaseButton block :loading="busy" @click="markDone">Marquer terminé</BaseButton>
          <BaseButton block variant="secondary" :disabled="busy" @click="rescheduling = true">
            Reprogrammer…
          </BaseButton>
          <BaseButton block variant="ghost" :disabled="busy" @click="snooze">
            Me rappeler demain
          </BaseButton>
        </div>

        <p v-if="queue.length > 1" class="mt-4 text-center text-xs text-muted">
          Encore {{ queue.length - 1 }} projet{{ queue.length > 2 ? 's' : '' }} à vérifier ensuite
        </p>
      </DialogContent>
    </DialogPortal>
  </DialogRoot>
</template>
