<script setup lang="ts">
/**
 * Drive files attached to a project or a task (SPEC §11): icon, name, open
 * in Drive; editors attach more through the Google Picker, or send a file
 * to the project's Drive folder. Hidden entirely when nothing is attached
 * and nothing can be (no Google on this server or for this user).
 */
import { ExternalLink, FolderUp, Link2, Trash2 } from 'lucide-vue-next'
import { computed, onMounted, ref, watch } from 'vue'

import { ApiError } from '@/api/client'
import { type DriveLink, integrationsApi } from '@/api/integrations'
import type { Project } from '@/api/projects'
import BaseButton from '@/components/ui/BaseButton.vue'
import { useGooglePicker } from '@/composables/useGooglePicker'
import { useUiStore } from '@/stores/ui'
import { formatSize } from '@/utils/files'

const props = defineProps<{
  project: Pick<Project, 'id' | 'drive_status'>
  taskId?: number
  canEdit: boolean
  /** Show the "send to the project's Drive" button (project level). */
  allowUpload?: boolean
}>()

const ui = useUiStore()
const picker = useGooglePicker()
const links = ref<DriveLink[] | null>(null)
const pickerUsable = ref(false)
const uploading = ref(false)
const input = ref<HTMLInputElement | null>(null)

const canUpload = computed(
  () => props.allowUpload && props.canEdit && props.project.drive_status === 'ok',
)

async function load() {
  links.value = await integrationsApi.driveLinks(
    props.taskId ? { task: props.taskId } : { project: props.project.id },
  )
}
watch(() => [props.project.id, props.taskId], load, { immediate: true })
onMounted(async () => {
  try {
    pickerUsable.value = (await integrationsApi.state()).google.picker
  } catch {
    pickerUsable.value = false
  }
})

async function attach() {
  const picked = await picker.pick(true)
  if (picker.error.value) ui.toast(picker.error.value, 'error')
  for (const file of picked) {
    try {
      await integrationsApi.attachDriveFile(props.project.id, file.id, props.taskId)
    } catch (error) {
      ui.toast(error instanceof ApiError ? error.message : `${file.name} non attaché.`, 'error')
    }
  }
  if (picked.length) {
    ui.toast(picked.length > 1 ? 'Fichiers Drive attachés' : 'Fichier Drive attaché', 'success')
    await load()
  }
}

async function upload(event: Event) {
  const file = (event.target as HTMLInputElement).files?.[0]
  if (!file) return
  uploading.value = true
  try {
    await integrationsApi.uploadToDrive(props.project.id, file)
    ui.toast('Fichier envoyé dans le dossier Drive du projet', 'success')
    await load()
  } catch (error) {
    ui.toast(error instanceof ApiError ? error.message : "L'envoi a échoué.", 'error')
  } finally {
    uploading.value = false
    if (input.value) input.value.value = ''
  }
}

async function remove(link: DriveLink) {
  try {
    await integrationsApi.removeDriveLink(link.id)
    links.value = (links.value ?? []).filter((current) => current.id !== link.id)
  } catch (error) {
    ui.toast(error instanceof ApiError ? error.message : 'Le lien est resté.', 'error')
  }
}
</script>

<template>
  <section
    v-if="(links && links.length) || (canEdit && (pickerUsable || canUpload))"
    class="space-y-2"
  >
    <div class="flex flex-wrap items-center gap-2">
      <h3 class="text-sm font-semibold">Fichiers Drive</h3>
      <div v-if="canEdit" class="ml-auto flex flex-wrap gap-1.5">
        <BaseButton
          v-if="pickerUsable"
          variant="secondary"
          size="sm"
          :loading="picker.opening.value"
          @click="attach"
        >
          <Link2 class="size-4" aria-hidden="true" /> Attacher depuis Drive
        </BaseButton>
        <BaseButton
          v-if="canUpload"
          variant="secondary"
          size="sm"
          :loading="uploading"
          @click="input?.click()"
        >
          <FolderUp class="size-4" aria-hidden="true" /> Envoyer dans le Drive du projet
        </BaseButton>
        <input
          ref="input"
          type="file"
          class="sr-only"
          aria-label="Fichier à envoyer sur Drive"
          @change="upload"
        />
      </div>
    </div>
    <ul
      v-if="links && links.length"
      class="divide-y divide-line rounded-xl border border-line bg-surface"
    >
      <li v-for="link in links" :key="link.id" class="flex items-center gap-3 px-3 py-2">
        <img v-if="link.icon_url" :src="link.icon_url" alt="" class="size-5 shrink-0" />
        <a
          :href="link.web_view_url || undefined"
          target="_blank"
          rel="noopener"
          class="min-w-0 flex-1 truncate text-sm hover:underline"
        >
          {{ link.name }}
        </a>
        <span v-if="link.size_bytes" class="shrink-0 text-xs text-muted">{{
          formatSize(link.size_bytes)
        }}</span>
        <a
          v-if="link.web_view_url"
          :href="link.web_view_url"
          target="_blank"
          rel="noopener"
          class="rounded-lg p-1.5 text-muted hover:bg-surface-2 hover:text-fg"
          aria-label="Ouvrir dans Drive"
          title="Ouvrir dans Drive"
        >
          <ExternalLink class="size-4" aria-hidden="true" />
        </a>
        <button
          v-if="canEdit"
          type="button"
          class="rounded-lg p-1.5 text-muted hover:bg-surface-2 hover:text-danger"
          aria-label="Détacher"
          title="Détacher (le fichier reste sur Drive)"
          @click="remove(link)"
        >
          <Trash2 class="size-4" aria-hidden="true" />
        </button>
      </li>
    </ul>
    <p v-else-if="links" class="text-xs text-muted">
      Aucun fichier Drive attaché{{ taskId ? ' à cette tâche' : '' }}.
    </p>
  </section>
</template>
