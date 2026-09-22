<script setup lang="ts">
/**
 * Upload panel: a new asset (file + name) or the next version of an existing
 * one (file + label + note). Drag-and-drop or picker, size checked before
 * sending, progress bar during the XHR, cancel possible.
 */
import { UploadCloud, X } from 'lucide-vue-next'
import { computed, ref, watch } from 'vue'

import { ApiError } from '@/api/client'
import { type Asset, type AssetVersion, filesApi } from '@/api/files'
import BaseButton from '@/components/ui/BaseButton.vue'
import BaseInput from '@/components/ui/BaseInput.vue'
import BaseTextarea from '@/components/ui/BaseTextarea.vue'
import FormError from '@/components/ui/FormError.vue'
import SidePanel from '@/components/ui/SidePanel.vue'
import { useUiStore } from '@/stores/ui'
import { ACCEPT, formatSize } from '@/utils/files'

const props = defineProps<{
  /** New asset in this project… */
  projectId?: number
  /** …or next version of this asset. */
  asset?: Asset | null
  maxUploadMb?: number
}>()
const emit = defineEmits<{ created: [asset: Asset]; versioned: [version: AssetVersion] }>()
const open = defineModel<boolean>('open', { required: true })

const ui = useUiStore()
const file = ref<File | null>(null)
const name = ref('')
const label = ref('')
const note = ref('')
const progress = ref<number | null>(null)
const error = ref('')
const dragging = ref(false)
const input = ref<HTMLInputElement | null>(null)
let controller: AbortController | null = null

const isVersion = computed(() => !!props.asset)
const limitMb = computed(() => props.maxUploadMb ?? 500)
const title = computed(() =>
  isVersion.value ? `Nouvelle version · ${props.asset!.name}` : 'Nouveau fichier',
)
const nextNumber = computed(() => (props.asset?.versions_count ?? 0) + 1)

watch(open, (value) => {
  if (!value) return
  file.value = null
  name.value = ''
  label.value = ''
  note.value = ''
  progress.value = null
  error.value = ''
})

function pick(candidate: File | undefined) {
  if (!candidate) return
  if (candidate.size > limitMb.value * 1024 * 1024) {
    error.value = `Fichier trop lourd (${limitMb.value} Mo max).`
    return
  }
  error.value = ''
  file.value = candidate
  // The asset takes the file's name, without its extension, unless typed.
  if (!isVersion.value && !name.value) name.value = candidate.name.replace(/\.[^.]+$/, '')
}

function onDrop(event: DragEvent) {
  dragging.value = false
  pick(event.dataTransfer?.files[0])
}

async function submit() {
  if (!file.value) return
  progress.value = 0
  error.value = ''
  controller = new AbortController()
  const onProgress = (ratio: number) => (progress.value = ratio)
  try {
    if (props.asset) {
      const version = await filesApi.addVersion(
        props.asset.id,
        file.value,
        { label: label.value.trim(), note: note.value.trim() },
        onProgress,
        controller.signal,
      )
      ui.toast(`v${version.number} envoyée`, 'success')
      emit('versioned', version)
    } else {
      const asset = await filesApi.create(
        file.value,
        {
          project: props.projectId!,
          name: name.value.trim() || file.value.name,
          label: label.value.trim(),
          note: note.value.trim(),
        },
        onProgress,
        controller.signal,
      )
      ui.toast('Fichier ajouté', 'success')
      emit('created', asset)
    }
    open.value = false
  } catch (caught) {
    if ((caught as Error).name === 'AbortError') return
    error.value =
      caught instanceof ApiError
        ? (caught.fieldErrors.file?.[0] ?? caught.message)
        : "L'envoi a échoué."
  } finally {
    progress.value = null
    controller = null
  }
}

function cancel() {
  controller?.abort()
  progress.value = null
}
</script>

<template>
  <SidePanel
    v-model:open="open"
    :title="title"
    :description="isVersion ? `v${nextNumber}` : undefined"
  >
    <form id="upload-form" class="space-y-4" @submit.prevent="submit">
      <div
        class="rounded-xl border-2 border-dashed p-6 text-center transition-colors"
        :class="dragging ? 'border-fg bg-surface-2' : 'border-line'"
        @dragover.prevent="dragging = true"
        @dragleave="dragging = false"
        @drop.prevent="onDrop"
      >
        <template v-if="file">
          <p class="truncate text-sm font-medium">{{ file.name }}</p>
          <p class="mt-1 text-xs text-muted">{{ formatSize(file.size) }}</p>
          <button
            v-if="progress === null"
            type="button"
            class="mt-2 inline-flex items-center gap-1 text-xs text-muted hover:text-fg"
            @click="file = null"
          >
            <X class="size-3.5" aria-hidden="true" /> Changer de fichier
          </button>
        </template>
        <template v-else>
          <UploadCloud class="mx-auto size-8 text-muted" aria-hidden="true" />
          <p class="mt-2 text-sm">Glisse un fichier ici, ou</p>
          <BaseButton variant="secondary" size="sm" class="mt-2" @click="input?.click()">
            Choisir un fichier
          </BaseButton>
          <p class="mt-2 text-xs text-muted">Audio, vidéo, image, PDF… {{ limitMb }} Mo max.</p>
        </template>
        <input
          ref="input"
          type="file"
          class="sr-only"
          :accept="ACCEPT"
          aria-label="Fichier à envoyer"
          @change="pick(($event.target as HTMLInputElement).files?.[0])"
        />
      </div>

      <BaseInput
        v-if="!isVersion"
        v-model="name"
        label="Nom"
        placeholder="Cover finale"
        required
        :disabled="progress !== null"
      />
      <BaseInput
        v-model="label"
        label="Libellé de la version"
        placeholder="mix 2, master, cover finale…"
        :disabled="progress !== null"
      />
      <BaseTextarea
        v-if="isVersion"
        v-model="note"
        label="Note"
        :rows="3"
        placeholder="Ce qui change dans cette version"
      />

      <div v-if="progress !== null" class="space-y-1.5">
        <div
          class="h-2 overflow-hidden rounded-full bg-surface-2"
          role="progressbar"
          :aria-valuenow="Math.round(progress * 100)"
          aria-valuemin="0"
          aria-valuemax="100"
          aria-label="Envoi"
        >
          <div class="h-full bg-fg transition-[width]" :style="{ width: `${progress * 100}%` }" />
        </div>
        <p class="text-xs text-muted">
          {{ progress < 1 ? `Envoi… ${Math.round(progress * 100)} %` : 'Traitement du fichier…' }}
        </p>
      </div>
      <FormError :message="error" />
    </form>
    <template #footer>
      <BaseButton v-if="progress !== null" variant="secondary" @click="cancel"
        >Annuler l'envoi</BaseButton
      >
      <BaseButton v-else variant="secondary" @click="open = false">Annuler</BaseButton>
      <BaseButton type="submit" form="upload-form" :loading="progress !== null" :disabled="!file">
        Envoyer
      </BaseButton>
    </template>
  </SidePanel>
</template>
